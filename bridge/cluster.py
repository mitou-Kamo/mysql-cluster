#!/usr/bin/env python3
"""
MySQL Cluster Bridge Interface for LineairDB Storage Engine.

This module provides the main interface for managing MySQL Group Replication
clusters where the primary node is a local MySQL installation running
LineairDB storage engine, and secondary nodes are either remote machines
or Docker containers.
"""

import os
import subprocess
import time
import json
import shutil
import logging
from pathlib import Path
from typing import Optional, Tuple, List, Dict, Any

from .config import ClusterConfig, NodeConfig, NodeType, NodeRole, create_default_config
from .primary import PrimaryNodeManager
from .secondary import SecondaryNodeManager

logger = logging.getLogger(__name__)


class ClusterBridge:
    """
    Main interface for MySQL Cluster management.
    
    This class acts as a bridge between LineairDB storage engine
    and MySQL Group Replication infrastructure.
    
    Usage:
        # Create a cluster with local primary and Docker secondaries
        bridge = ClusterBridge.create(num_secondaries=5)
        bridge.setup()
        bridge.start()
        
        # Or with remote machines
        bridge = ClusterBridge.create(
            num_secondaries=3,
            remote_hosts=[
                {"host": "192.168.1.10", "ssh_user": "mysql"},
                {"host": "192.168.1.11", "ssh_user": "mysql"},
            ]
        )
    """
    
    def __init__(self, config: ClusterConfig):
        """
        Initialize the Cluster Bridge.
        
        Args:
            config: Cluster configuration
        """
        self.config = config
        self.primary_manager = PrimaryNodeManager(config)
        self.secondary_manager = SecondaryNodeManager(config)
        
        # Set up logging
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
    
    @classmethod
    def create(
        cls,
        num_secondaries: int = 2,
        primary_type: NodeType = NodeType.LOCAL_SYSTEMCTL,
        remote_hosts: Optional[List[Dict[str, str]]] = None,
        base_dir: Optional[Path] = None,
        cluster_name: str = "lineairdb_cluster",
    ) -> "ClusterBridge":
        """
        Create a new ClusterBridge with specified configuration.
        
        Args:
            num_secondaries: Number of secondary nodes
            primary_type: Type of primary node (LOCAL_SYSTEMCTL or LOCAL_BINARY)
            remote_hosts: Optional list of remote host configurations
            base_dir: Base directory for cluster files
            cluster_name: Name of the cluster
            
        Returns:
            Configured ClusterBridge instance
        """
        config = create_default_config(
            num_secondaries=num_secondaries,
            primary_type=primary_type,
            remote_hosts=remote_hosts,
            base_dir=base_dir,
        )
        config.cluster_name = cluster_name
        
        return cls(config)
    
    @classmethod
    def load(cls, config_path: Path) -> "ClusterBridge":
        """
        Load a ClusterBridge from a saved configuration.
        
        Args:
            config_path: Path to the configuration file
            
        Returns:
            ClusterBridge instance
        """
        config = ClusterConfig.load(config_path)
        return cls(config)
    
    def save(self, filepath: Optional[Path] = None) -> Path:
        """
        Save the cluster configuration.
        
        Args:
            filepath: Optional path to save to
            
        Returns:
            Path to the saved configuration
        """
        return self.config.save(filepath)
    
    def setup(self) -> Dict[str, Any]:
        """
        Set up the cluster infrastructure.
        
        This prepares all necessary files and directories but does not
        start any services.
        
        Returns:
            Dictionary with setup results
        """
        results = {
            "success": True,
            "steps": [],
        }
        
        # Create directories
        logger.info("Creating directories...")
        try:
            self.config.config_dir.mkdir(parents=True, exist_ok=True)
            self.config.data_dir.mkdir(parents=True, exist_ok=True)
            self.config.logs_dir.mkdir(parents=True, exist_ok=True)
            (self.config.data_dir / "primary").mkdir(parents=True, exist_ok=True)
            results["steps"].append({"name": "create_directories", "success": True})
        except Exception as e:
            results["success"] = False
            results["steps"].append({"name": "create_directories", "success": False, "error": str(e)})
            return results
        
        # Generate configuration files
        logger.info("Generating configuration files...")
        try:
            self.primary_manager.generate_config_file()
            self.secondary_manager.generate_secondary_configs()
            results["steps"].append({"name": "generate_configs", "success": True})
        except Exception as e:
            results["success"] = False
            results["steps"].append({"name": "generate_configs", "success": False, "error": str(e)})
            return results
        
        # Generate docker-compose for Docker secondaries
        docker_nodes = self.secondary_manager.get_docker_nodes()
        if docker_nodes:
            logger.info(f"Generating docker-compose for {len(docker_nodes)} containers...")
            try:
                self.secondary_manager.generate_docker_compose()
                results["steps"].append({"name": "generate_docker_compose", "success": True})
            except Exception as e:
                results["success"] = False
                results["steps"].append({"name": "generate_docker_compose", "success": False, "error": str(e)})
        
        # Save configuration
        try:
            config_path = self.save()
            results["steps"].append({"name": "save_config", "success": True, "path": str(config_path)})
        except Exception as e:
            results["steps"].append({"name": "save_config", "success": False, "error": str(e)})
        
        logger.info("Setup completed")
        return results
    
    def start(self, setup_replication: bool = True) -> Dict[str, Any]:
        """
        Start the entire cluster.
        
        Args:
            setup_replication: Whether to configure group replication
            
        Returns:
            Dictionary with start results
        """
        results = {
            "success": True,
            "primary": None,
            "secondaries": None,
            "replication": None,
        }
        
        # Start primary node
        logger.info("Starting primary node...")
        success, msg = self.primary_manager.start()
        results["primary"] = {"success": success, "message": msg}
        if not success:
            results["success"] = False
            logger.error(f"Failed to start primary: {msg}")
            return results
        
        # Wait for primary to be ready
        logger.info("Waiting for primary node to be ready...")
        time.sleep(10)
        
        # Start secondary nodes
        logger.info("Starting secondary nodes...")
        sec_results = self.secondary_manager.start_all()
        results["secondaries"] = sec_results
        
        if not sec_results["docker"]["success"] or not sec_results["remote"]["success"]:
            results["success"] = False
            logger.warning("Some secondary nodes failed to start")
        
        # Wait for secondaries to be ready
        logger.info("Waiting for secondary nodes to be ready...")
        time.sleep(30)
        
        # Set up group replication
        if setup_replication:
            logger.info("Setting up group replication...")
            repl_results = self.setup_group_replication()
            results["replication"] = repl_results
            if not repl_results.get("success"):
                results["success"] = False
        
        return results
    
    def stop(self) -> Dict[str, Any]:
        """
        Stop the entire cluster.
        
        Returns:
            Dictionary with stop results
        """
        results = {
            "success": True,
            "primary": None,
            "secondaries": None,
        }
        
        # Stop secondary nodes first
        logger.info("Stopping secondary nodes...")
        sec_results = self.secondary_manager.stop_all()
        results["secondaries"] = sec_results
        
        # Stop primary node
        logger.info("Stopping primary node...")
        success, msg = self.primary_manager.stop()
        results["primary"] = {"success": success, "message": msg}
        
        if not success:
            results["success"] = False
        
        return results
    
    def restart(self) -> Dict[str, Any]:
        """
        Restart the entire cluster.
        
        Returns:
            Dictionary with restart results
        """
        logger.info("Restarting cluster...")
        self.stop()
        time.sleep(5)
        return self.start(setup_replication=False)
    
    def setup_group_replication(self) -> Dict[str, Any]:
        """
        Set up MySQL Group Replication on all nodes.
        
        Returns:
            Dictionary with replication setup results
        """
        results = {
            "success": True,
            "steps": [],
        }
        
        # Configure primary for group replication
        logger.info("Configuring primary for group replication...")
        success, msg = self.primary_manager.configure_for_group_replication()
        results["steps"].append({
            "name": "configure_primary",
            "success": success,
            "message": msg
        })
        if not success:
            results["success"] = False
            return results
        
        # Create the cluster
        logger.info("Creating InnoDB cluster...")
        success, msg = self.primary_manager.create_cluster()
        results["steps"].append({
            "name": "create_cluster",
            "success": success,
            "message": msg
        })
        if not success:
            results["success"] = False
            return results
        
        # Configure and add each secondary
        for node in self.config.secondaries:
            logger.info(f"Adding secondary node {node.node_id}...")
            
            # Configure the secondary
            if node.node_type == NodeType.REMOTE_MACHINE:
                success, msg = self.secondary_manager.configure_remote_node(node)
            else:
                # Docker container - configure via MySQL Shell from host
                success, msg = self._configure_docker_secondary(node)
            
            results["steps"].append({
                "name": f"configure_secondary_{node.node_id}",
                "success": success,
                "message": msg
            })
            
            if not success:
                logger.warning(f"Failed to configure secondary {node.node_id}: {msg}")
                continue
            
            # Add to cluster
            success, msg = self._add_node_to_cluster(node)
            results["steps"].append({
                "name": f"add_secondary_{node.node_id}",
                "success": success,
                "message": msg
            })
            
            if not success:
                logger.warning(f"Failed to add secondary {node.node_id} to cluster: {msg}")
        
        # Get final cluster status
        success, status = self.primary_manager.get_cluster_status()
        results["cluster_status"] = status if success else "Unable to get status"
        
        return results
    
    def _configure_docker_secondary(self, node: NodeConfig) -> Tuple[bool, str]:
        """Configure a Docker secondary node."""
        mysqlsh = self.config.mysqlsh_path or "mysqlsh"
        uri = node.get_connection_uri()
        
        script = f"""
print('Configuring Docker secondary instance...');
try {{
    dba.configureInstance('{uri}');
    print('Instance configured successfully');
}} catch(e) {{
    if (e.message.includes('already configured') || e.message.includes('already been configured')) {{
        print('Instance already configured');
    }} else {{
        print('Error: ' + e.message);
        throw e;
    }}
}}
"""
        
        try:
            result = subprocess.run(
                [mysqlsh, uri, "--js", "--no-wizard", "-e", script],
                capture_output=True,
                text=True,
                timeout=120
            )
            if result.returncode != 0:
                return False, result.stderr
            return True, result.stdout
        except Exception as e:
            return False, str(e)
    
    def _add_node_to_cluster(self, node: NodeConfig) -> Tuple[bool, str]:
        """Add a node to the InnoDB cluster."""
        primary_uri = self.config.primary.get_connection_uri()
        node_uri = node.get_connection_uri()
        cluster_name = self.config.cluster_name
        local_address = node.get_local_address()
        
        script = f"""
var cluster = dba.getCluster('{cluster_name}');
print('Adding instance to cluster...');
try {{
    cluster.addInstance('{node_uri}', {{
        recoveryMethod: 'clone',
        localAddress: '{local_address}'
    }});
    print('Instance added successfully');
}} catch(e) {{
    if (e.message.includes('already a member') || e.message.includes('is already part')) {{
        print('Instance is already a member of the cluster');
    }} else {{
        print('Error: ' + e.message);
        throw e;
    }}
}}
"""
        
        mysqlsh = self.config.mysqlsh_path or "mysqlsh"
        
        try:
            result = subprocess.run(
                [mysqlsh, primary_uri, "--js", "--no-wizard", "-e", script],
                capture_output=True,
                text=True,
                timeout=300  # Clone can take a while
            )
            if result.returncode != 0:
                return False, result.stderr
            return True, result.stdout
        except Exception as e:
            return False, str(e)
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get the status of the entire cluster.
        
        Returns:
            Dictionary with cluster status
        """
        status = {
            "cluster_name": self.config.cluster_name,
            "primary": self.primary_manager.get_status(),
            "secondaries": self.secondary_manager.get_status(),
            "cluster": None,
        }
        
        # Get InnoDB cluster status
        if status["primary"]["running"]:
            success, cluster_status = self.primary_manager.get_cluster_status()
            if success:
                try:
                    status["cluster"] = json.loads(cluster_status)
                except json.JSONDecodeError:
                    status["cluster"] = cluster_status
        
        return status
    
    def scale(self, target_secondaries: int) -> Dict[str, Any]:
        """
        Scale the number of secondary nodes.
        
        Currently only supports scaling Docker containers.
        
        Args:
            target_secondaries: Target number of secondary nodes
            
        Returns:
            Dictionary with scaling results
        """
        results = {
            "success": True,
            "previous_count": len(self.config.secondaries),
            "target_count": target_secondaries,
        }
        
        # Calculate how many Docker nodes we need
        remote_count = len(self.secondary_manager.get_remote_nodes())
        docker_target = target_secondaries - remote_count
        
        if docker_target < 0:
            docker_target = 0
        
        logger.info(f"Scaling Docker nodes to {docker_target}...")
        success, msg = self.secondary_manager.scale_docker_nodes(docker_target)
        results["success"] = success
        results["message"] = msg
        
        # If successful, add new nodes to cluster
        if success and docker_target > len(self.secondary_manager.get_docker_nodes()):
            logger.info("Adding new nodes to cluster...")
            for node in self.config.secondaries:
                if not node.is_reachable():
                    continue
                success, msg = self._configure_docker_secondary(node)
                if success:
                    self._add_node_to_cluster(node)
        
        results["current_count"] = len(self.config.secondaries)
        return results
    
    def add_remote_secondary(
        self,
        host: str,
        ssh_user: str,
        ssh_key_path: Optional[str] = None,
    ) -> Tuple[bool, str]:
        """
        Add a remote machine as a secondary node.
        
        Args:
            host: IP address or hostname of the remote machine
            ssh_user: SSH user for the remote machine
            ssh_key_path: Optional path to SSH key
            
        Returns:
            Tuple of (success, message)
        """
        # Add to configuration
        node = self.config.add_secondary(
            host=host,
            ssh_user=ssh_user,
            ssh_key_path=ssh_key_path,
            node_type=NodeType.REMOTE_MACHINE,
        )
        
        # Check if reachable
        check_result = self.secondary_manager.check_remote_node(node)
        if not check_result["reachable"]:
            return False, f"Cannot reach {host}"
        
        if not check_result["mysql_running"]:
            # Try to start MySQL
            success, msg = self.secondary_manager.start_remote_node(node)
            if not success:
                return False, f"Cannot start MySQL on {host}: {msg}"
        
        # Configure for group replication
        success, msg = self.secondary_manager.configure_remote_node(node)
        if not success:
            return False, f"Cannot configure MySQL on {host}: {msg}"
        
        # Add to cluster
        success, msg = self._add_node_to_cluster(node)
        if not success:
            return False, f"Cannot add {host} to cluster: {msg}"
        
        # Save configuration
        self.save()
        
        return True, f"Successfully added {host} as secondary node"
    
    def remove_secondary(self, node_id: int) -> Tuple[bool, str]:
        """
        Remove a secondary node from the cluster.
        
        Args:
            node_id: ID of the node to remove
            
        Returns:
            Tuple of (success, message)
        """
        # Find the node
        node = None
        for n in self.config.secondaries:
            if n.node_id == node_id:
                node = n
                break
        
        if not node:
            return False, f"Node {node_id} not found"
        
        # Remove from cluster via MySQL Shell
        primary_uri = self.config.primary.get_connection_uri()
        node_uri = node.get_connection_uri()
        cluster_name = self.config.cluster_name
        
        script = f"""
var cluster = dba.getCluster('{cluster_name}');
print('Removing instance from cluster...');
try {{
    cluster.removeInstance('{node_uri}', {{force: true}});
    print('Instance removed successfully');
}} catch(e) {{
    print('Error: ' + e.message);
}}
"""
        
        mysqlsh = self.config.mysqlsh_path or "mysqlsh"
        
        try:
            subprocess.run(
                [mysqlsh, primary_uri, "--js", "--no-wizard", "-e", script],
                capture_output=True,
                text=True,
                timeout=60
            )
        except Exception as e:
            logger.warning(f"Error removing node from cluster: {e}")
        
        # Stop and remove Docker container if applicable
        if node.node_type == NodeType.DOCKER_CONTAINER:
            try:
                subprocess.run(
                    ["docker", "rm", "-f", node.container_name],
                    capture_output=True,
                    timeout=30
                )
            except Exception:
                pass
        
        # Remove from configuration
        self.config.secondaries.remove(node)
        self.save()
        
        return True, f"Removed node {node_id}"
    
    def check_lineairdb(self) -> Dict[str, Any]:
        """
        Check LineairDB storage engine availability on all nodes.
        
        Returns:
            Dictionary with LineairDB status on each node
        """
        results = {
            "primary": None,
            "secondaries": [],
        }
        
        # Check primary
        available, msg = self.primary_manager.check_lineairdb_plugin()
        results["primary"] = {"available": available, "message": msg}
        
        # Check secondaries
        for node in self.config.secondaries:
            if not node.is_reachable():
                results["secondaries"].append({
                    "node_id": node.node_id,
                    "available": False,
                    "message": "Node not reachable"
                })
                continue
            
            # Execute check via MySQL
            uri = node.get_connection_uri()
            mysqlsh = self.config.mysqlsh_path or "mysqlsh"
            
            try:
                result = subprocess.run(
                    [
                        mysqlsh, uri, "--sql", "--no-wizard",
                        "-e", "SHOW PLUGINS WHERE Name='lineairdb';"
                    ],
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                available = "lineairdb" in result.stdout.lower()
                results["secondaries"].append({
                    "node_id": node.node_id,
                    "available": available,
                    "message": "LineairDB available" if available else "LineairDB not installed"
                })
            except Exception as e:
                results["secondaries"].append({
                    "node_id": node.node_id,
                    "available": False,
                    "message": str(e)
                })
        
        return results
    
    def install_lineairdb_plugin(
        self,
        plugin_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Install LineairDB storage engine plugin on all nodes.
        
        This function copies the plugin to each node and installs it.
        The plugin is expected to be built in the LineairDB-storage-engine directory.
        
        Args:
            plugin_path: Path to the plugin file. If not provided, will try to
                        find it in common locations relative to this repository.
        
        Returns:
            Dictionary with installation results for each node
        
        Example:
            # Install from LineairDB-storage-engine build directory
            cluster.install_lineairdb_plugin(
                "/path/to/LineairDB-storage-engine/build/ha_lineairdb.so"
            )
            
            # Or let it auto-detect (assumes this repo is a submodule)
            cluster.install_lineairdb_plugin()
        """
        results = {
            "success": True,
            "primary": None,
            "secondaries": None,
            "plugin_path": None,
        }
        
        # Find plugin path if not provided
        if plugin_path is None:
            plugin_path = self._find_lineairdb_plugin()
        
        if plugin_path is None:
            results["success"] = False
            results["error"] = "LineairDB plugin not found. Please provide the plugin path."
            return results
        
        if not os.path.exists(plugin_path):
            results["success"] = False
            results["error"] = f"Plugin file not found: {plugin_path}"
            return results
        
        results["plugin_path"] = plugin_path
        logger.info(f"Using LineairDB plugin: {plugin_path}")
        
        # Install on primary node
        logger.info("Installing LineairDB plugin on primary node...")
        primary_success, primary_msg = self.primary_manager.install_lineairdb_plugin(plugin_path)
        results["primary"] = {
            "success": primary_success,
            "message": primary_msg,
        }
        if not primary_success:
            results["success"] = False
            logger.warning(f"Failed to install plugin on primary: {primary_msg}")
        else:
            logger.info("Successfully installed plugin on primary node")
        
        # Install on secondary nodes
        logger.info("Installing LineairDB plugin on secondary nodes...")
        sec_results = self.secondary_manager.install_lineairdb_plugin_on_all(plugin_path)
        results["secondaries"] = sec_results
        
        if not sec_results["success"]:
            results["success"] = False
        
        # Summary
        total_nodes = 1 + len(self.config.secondaries)
        successful_nodes = (1 if primary_success else 0) + sum(
            1 for n in sec_results.get("nodes", []) if n.get("success")
        )
        results["summary"] = f"Installed on {successful_nodes}/{total_nodes} nodes"
        
        return results
    
    def _find_lineairdb_plugin(self) -> Optional[str]:
        """
        Try to find the LineairDB plugin in common locations.
        
        Assumes this repository is a submodule of LineairDB-storage-engine.
        
        Returns:
            Path to the plugin file, or None if not found
        """
        # Common plugin filenames
        plugin_names = [
            "ha_lineairdb.so",
            "ha_lineairdb_storage_engine.so",
        ]
        
        # Common search locations relative to this repository
        # Assuming: LineairDB-storage-engine/cluster/ (this repo as submodule)
        search_paths = [
            # Parent directory (LineairDB-storage-engine)
            self.config.base_dir.parent / "build",
            self.config.base_dir.parent / "build" / "Release",
            self.config.base_dir.parent / "build" / "Debug",
            # Sibling directories
            self.config.base_dir.parent / "plugins",
            # Absolute paths for common installations
            Path("/usr/lib/mysql/plugin"),
            Path("/usr/lib64/mysql/plugin"),
            Path("/usr/local/mysql/lib/plugin"),
        ]
        
        for search_path in search_paths:
            for plugin_name in plugin_names:
                plugin_path = search_path / plugin_name
                if plugin_path.exists():
                    logger.info(f"Found LineairDB plugin at: {plugin_path}")
                    return str(plugin_path)
        
        logger.warning("Could not find LineairDB plugin automatically")
        return None


# Convenience functions for LineairDB integration
def create_cluster(
    num_secondaries: int = 2,
    remote_hosts: Optional[List[Dict[str, str]]] = None,
) -> ClusterBridge:
    """
    Create and set up a new MySQL cluster for LineairDB.
    
    This is the main entry point for LineairDB storage engine integration.
    
    Args:
        num_secondaries: Number of secondary nodes
        remote_hosts: Optional list of remote machine configurations
        
    Returns:
        Configured and ready ClusterBridge instance
    
    Example:
        # Create cluster with 10 Docker secondary nodes
        cluster = create_cluster(num_secondaries=10)
        cluster.start()
        
        # Create cluster with remote machines (Docker fallback for extras)
        cluster = create_cluster(
            num_secondaries=5,
            remote_hosts=[
                {"host": "192.168.1.10", "ssh_user": "mysql"},
                {"host": "192.168.1.11", "ssh_user": "mysql"},
            ]
        )
        # 2 remote machines + 3 Docker containers
    """
    bridge = ClusterBridge.create(
        num_secondaries=num_secondaries,
        remote_hosts=remote_hosts,
    )
    bridge.setup()
    return bridge


def load_cluster(config_path: Optional[Path] = None) -> ClusterBridge:
    """
    Load an existing cluster configuration.
    
    Args:
        config_path: Path to configuration file (defaults to ./config/cluster.json)
        
    Returns:
        ClusterBridge instance
    """
    if config_path is None:
        config_path = Path.cwd() / "config" / "cluster.json"
    
    return ClusterBridge.load(config_path)

