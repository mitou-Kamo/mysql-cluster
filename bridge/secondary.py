#!/usr/bin/env python3
"""
Secondary Node Manager for MySQL Cluster Bridge.

Manages secondary MySQL nodes which can be either:
- Remote machines with MySQL installed
- Docker containers (auto-created if remote machines not available)
"""

import os
import subprocess
import time
import json
from pathlib import Path
from typing import Optional, Tuple, List, Dict, Any
import logging

from .config import NodeConfig, NodeType, NodeRole, ClusterConfig

logger = logging.getLogger(__name__)


class SecondaryNodeManager:
    """
    Manages secondary MySQL nodes.
    
    Supports:
    - Remote machines via SSH
    - Docker containers (auto-scaling)
    """
    
    def __init__(self, config: ClusterConfig):
        """
        Initialize the Secondary Node Manager.
        
        Args:
            config: Cluster configuration
        """
        self.config = config
        self.docker_compose_path = config.base_dir / "docker-compose-secondaries.yml"
    
    def get_secondary_nodes(self) -> List[NodeConfig]:
        """Get all secondary node configurations."""
        return self.config.secondaries
    
    def get_docker_nodes(self) -> List[NodeConfig]:
        """Get secondary nodes that are Docker containers."""
        return [n for n in self.config.secondaries if n.node_type == NodeType.DOCKER_CONTAINER]
    
    def get_remote_nodes(self) -> List[NodeConfig]:
        """Get secondary nodes that are remote machines."""
        return [n for n in self.config.secondaries if n.node_type == NodeType.REMOTE_MACHINE]
    
    def _run_ssh_command(
        self,
        node: NodeConfig,
        command: str,
        timeout: int = 30
    ) -> Tuple[bool, str]:
        """
        Run a command on a remote machine via SSH.
        
        Args:
            node: Node configuration
            command: Command to execute
            timeout: Timeout in seconds
            
        Returns:
            Tuple of (success, output/error)
        """
        try:
            ssh_cmd = ["ssh"]
            
            if node.ssh_key_path:
                ssh_cmd.extend(["-i", node.ssh_key_path])
            
            ssh_cmd.extend([
                "-o", "StrictHostKeyChecking=no",
                "-o", "ConnectTimeout=10",
                "-p", str(node.ssh_port),
                f"{node.ssh_user}@{node.host}",
                command
            ])
            
            result = subprocess.run(
                ssh_cmd,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            
            if result.returncode != 0:
                return False, result.stderr
            return True, result.stdout
        
        except subprocess.TimeoutExpired:
            return False, "SSH command timed out"
        except Exception as e:
            return False, str(e)
    
    def check_remote_node(self, node: NodeConfig) -> Dict[str, Any]:
        """
        Check if a remote node is available and MySQL is running.
        
        Args:
            node: Node configuration
            
        Returns:
            Dictionary with check results
        """
        result = {
            "node_id": node.node_id,
            "host": node.host,
            "reachable": False,
            "ssh_accessible": False,
            "mysql_running": False,
            "mysql_version": None,
        }
        
        # Check if reachable via network
        result["reachable"] = node.is_reachable()
        
        if node.ssh_user:
            # Check SSH access
            success, output = self._run_ssh_command(node, "echo ok")
            result["ssh_accessible"] = success
            
            if success:
                # Check MySQL status
                success, output = self._run_ssh_command(
                    node,
                    "systemctl is-active mysql || systemctl is-active mysqld"
                )
                result["mysql_running"] = success and "active" in output
                
                # Get MySQL version
                success, output = self._run_ssh_command(
                    node,
                    "mysql --version 2>/dev/null || mysqld --version 2>/dev/null"
                )
                if success:
                    result["mysql_version"] = output.strip()
        
        return result
    
    def start_remote_node(self, node: NodeConfig) -> Tuple[bool, str]:
        """
        Start MySQL on a remote node via SSH.
        
        Args:
            node: Node configuration
            
        Returns:
            Tuple of (success, message)
        """
        if not node.ssh_user:
            return False, "SSH user not configured"
        
        success, output = self._run_ssh_command(
            node,
            "sudo systemctl start mysql || sudo systemctl start mysqld",
            timeout=60
        )
        
        if success:
            # Wait for MySQL to be ready
            for _ in range(30):
                time.sleep(1)
                if node.is_reachable():
                    return True, "MySQL started successfully"
            return False, "MySQL started but not responding"
        
        return False, f"Failed to start MySQL: {output}"
    
    def stop_remote_node(self, node: NodeConfig) -> Tuple[bool, str]:
        """
        Stop MySQL on a remote node via SSH.
        
        Args:
            node: Node configuration
            
        Returns:
            Tuple of (success, message)
        """
        if not node.ssh_user:
            return False, "SSH user not configured"
        
        success, output = self._run_ssh_command(
            node,
            "sudo systemctl stop mysql || sudo systemctl stop mysqld",
            timeout=60
        )
        
        return success, output if not success else "MySQL stopped successfully"
    
    def configure_remote_node(self, node: NodeConfig) -> Tuple[bool, str]:
        """
        Configure a remote node for group replication via MySQL Shell.
        
        Args:
            node: Node configuration
            
        Returns:
            Tuple of (success, message)
        """
        mysqlsh = self.config.mysqlsh_path or "mysqlsh"
        uri = node.get_connection_uri()
        
        script = f"""
print('Configuring remote secondary instance...');
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
    
    def generate_docker_compose(self) -> Path:
        """
        Generate docker-compose file for secondary Docker containers.
        
        Returns:
            Path to the generated docker-compose file
        """
        docker_nodes = self.get_docker_nodes()
        
        if not docker_nodes:
            logger.info("No Docker secondary nodes configured")
            return self.docker_compose_path
        
        services = {}
        
        for node in docker_nodes:
            server_id = node.server_id or node.node_id
            host_port = 33060 + node.node_id
            
            # Use configurable image (custom Ubuntu or official Oracle Linux)
            docker_image = self.config.get_docker_image()
            
            service = {
                "image": docker_image,
                "container_name": node.container_name,
                "hostname": node.container_name,
                "environment": {
                    "MYSQL_ROOT_PASSWORD": self.config.mysql_root_password,
                    "MYSQL_DATABASE": self.config.mysql_database,
                    "MYSQL_USER": self.config.mysql_user,
                    "MYSQL_PASSWORD": self.config.mysql_user_password,
                    "MYSQL_SERVER_ID": str(server_id),  # For Ubuntu image entrypoint
                },
                "ports": [f"{host_port}:3306"],
                "volumes": [
                    f"./config/secondary{node.node_id - 1}.cnf:/etc/mysql/conf.d/custom.cnf",
                    f"./data/secondary{node.node_id - 1}:/var/lib/mysql",
                ],
                "networks": {
                    self.config.docker_network_name: {
                        "ipv4_address": node.docker_ip,
                    }
                },
                "command": (
                    f"mysqld --server-id={server_id} "
                    "--log-bin=mysql-bin "
                    "--gtid-mode=ON "
                    "--enforce-gtid-consistency=ON "
                    "--binlog-format=ROW "
                    "--relay-log=mysql-relay-bin"
                ),
                "restart": "unless-stopped",
                "healthcheck": {
                    "test": [
                        "CMD", "mysqladmin", "ping", "-h", "localhost",
                        "-u", "root", f"-p{self.config.mysql_root_password}"
                    ],
                    "interval": "10s",
                    "timeout": "5s",
                    "retries": 5,
                },
            }
            
            services[node.container_name] = service
        
        compose_config = {
            "version": "3.3",
            "services": services,
            "networks": {
                self.config.docker_network_name: {
                    "driver": "bridge",
                    "ipam": {
                        "config": [
                            {"subnet": self.config.docker_network_subnet}
                        ]
                    }
                }
            }
        }
        
        # Write docker-compose file
        import yaml
        self.docker_compose_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(self.docker_compose_path, "w") as f:
            yaml.dump(compose_config, f, default_flow_style=False)
        
        return self.docker_compose_path
    
    def generate_secondary_configs(self) -> List[Path]:
        """
        Generate MySQL configuration files for all secondary nodes.
        
        Returns:
            List of paths to generated configuration files
        """
        config_paths = []
        
        for node in self.config.secondaries:
            config_content = f"""[mysqld]
# Server Configuration
server-id = {node.server_id or node.node_id}
bind-address = 0.0.0.0
port = 3306

# Replication Configuration
log-bin = mysql-bin
binlog-format = ROW
gtid-mode = ON
enforce-gtid-consistency = ON
relay-log = mysql-relay-bin
relay-log-recovery = 1

# Group Replication Configuration
# Note: Group Replication settings will be configured via MySQL Shell

# Storage Engine Configuration
default-storage-engine = InnoDB

# Performance Tuning
innodb_buffer_pool_size = 1G
innodb_log_file_size = 256M
max_connections = 200
max_allowed_packet = 256M

# LineairDB Support (if plugin is available)
# plugin-load-add = ha_lineairdb.so
"""
            
            config_path = self.config.config_dir / f"secondary{node.node_id - 1}.cnf"
            config_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(config_path, "w") as f:
                f.write(config_content)
            
            config_paths.append(config_path)
        
        return config_paths
    
    def check_docker_image_exists(self) -> Tuple[bool, str]:
        """
        Check if the configured Docker image exists.
        
        Returns:
            Tuple of (exists, message)
        """
        docker_image = self.config.get_docker_image()
        
        try:
            result = subprocess.run(
                ["docker", "image", "inspect", docker_image],
                capture_output=True,
                text=True,
                timeout=30
            )
            if result.returncode == 0:
                return True, f"Image '{docker_image}' is available"
            return False, f"Image '{docker_image}' not found. Run 'mysql-cluster-bridge build-image' to build it."
        except Exception as e:
            return False, f"Failed to check Docker image: {e}"
    
    def _try_build_image(self) -> Tuple[bool, str]:
        """
        Try to build the custom Docker image.
        
        Returns:
            Tuple of (success, message)
        """
        docker_dir = self.config.docker_dir
        dockerfile_path = docker_dir / "Dockerfile.ubuntu"
        
        if not dockerfile_path.exists():
            return False, f"Dockerfile not found at {dockerfile_path}"
        
        docker_image = self.config.docker_image
        
        try:
            logger.info(f"Building Docker image '{docker_image}'...")
            result = subprocess.run(
                [
                    "docker", "build",
                    "-t", docker_image,
                    "-f", str(dockerfile_path),
                    str(docker_dir)
                ],
                capture_output=True,
                text=True,
                timeout=600  # 10 minutes for build
            )
            
            if result.returncode != 0:
                return False, f"Build failed: {result.stderr}"
            
            logger.info(f"Successfully built Docker image '{docker_image}'")
            return True, f"Image '{docker_image}' built successfully"
        except subprocess.TimeoutExpired:
            return False, "Build timed out after 10 minutes"
        except Exception as e:
            return False, str(e)
    
    def start_docker_containers(self) -> Tuple[bool, str]:
        """
        Start all Docker container secondary nodes.
        
        Returns:
            Tuple of (success, message)
        """
        docker_nodes = self.get_docker_nodes()
        
        if not docker_nodes:
            return True, "No Docker secondary nodes to start"
        
        # Check if custom image is required and exists
        if self.config.use_custom_image:
            exists, msg = self.check_docker_image_exists()
            if not exists:
                logger.warning(msg)
                logger.info("Attempting to build the Docker image...")
                # Try to build the image if it doesn't exist
                build_success, build_msg = self._try_build_image()
                if not build_success:
                    return False, f"Docker image not available: {msg}. Build failed: {build_msg}"
        
        # Generate docker-compose file
        self.generate_docker_compose()
        
        # Generate config files
        self.generate_secondary_configs()
        
        # Create data directories
        for node in docker_nodes:
            data_dir = self.config.data_dir / f"secondary{node.node_id - 1}"
            data_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            result = subprocess.run(
                ["docker-compose", "-f", str(self.docker_compose_path), "up", "-d"],
                capture_output=True,
                text=True,
                cwd=str(self.config.base_dir),
                timeout=300
            )
            
            if result.returncode != 0:
                return False, f"Failed to start containers: {result.stderr}"
            
            # Wait for containers to be ready
            logger.info("Waiting for containers to be ready...")
            time.sleep(30)
            
            return True, f"Started {len(docker_nodes)} Docker containers"
        
        except subprocess.TimeoutExpired:
            return False, "Timeout starting Docker containers"
        except Exception as e:
            return False, str(e)
    
    def stop_docker_containers(self) -> Tuple[bool, str]:
        """
        Stop all Docker container secondary nodes.
        
        Returns:
            Tuple of (success, message)
        """
        if not self.docker_compose_path.exists():
            return True, "No docker-compose file found"
        
        try:
            result = subprocess.run(
                ["docker-compose", "-f", str(self.docker_compose_path), "down"],
                capture_output=True,
                text=True,
                cwd=str(self.config.base_dir),
                timeout=120
            )
            
            if result.returncode != 0:
                return False, f"Failed to stop containers: {result.stderr}"
            
            return True, "Docker containers stopped"
        
        except Exception as e:
            return False, str(e)
    
    def start_all(self) -> Dict[str, Any]:
        """
        Start all secondary nodes (both remote and Docker).
        
        Returns:
            Dictionary with start results for each node type
        """
        results = {
            "docker": {"success": True, "message": "", "nodes": []},
            "remote": {"success": True, "message": "", "nodes": []},
        }
        
        # Start Docker containers
        docker_nodes = self.get_docker_nodes()
        if docker_nodes:
            success, msg = self.start_docker_containers()
            results["docker"]["success"] = success
            results["docker"]["message"] = msg
            results["docker"]["nodes"] = [n.container_name for n in docker_nodes]
        
        # Start remote nodes
        remote_nodes = self.get_remote_nodes()
        for node in remote_nodes:
            success, msg = self.start_remote_node(node)
            results["remote"]["nodes"].append({
                "host": node.host,
                "success": success,
                "message": msg
            })
            if not success:
                results["remote"]["success"] = False
        
        return results
    
    def stop_all(self) -> Dict[str, Any]:
        """
        Stop all secondary nodes (both remote and Docker).
        
        Returns:
            Dictionary with stop results for each node type
        """
        results = {
            "docker": {"success": True, "message": ""},
            "remote": {"success": True, "nodes": []},
        }
        
        # Stop Docker containers
        success, msg = self.stop_docker_containers()
        results["docker"]["success"] = success
        results["docker"]["message"] = msg
        
        # Stop remote nodes
        for node in self.get_remote_nodes():
            success, msg = self.stop_remote_node(node)
            results["remote"]["nodes"].append({
                "host": node.host,
                "success": success,
                "message": msg
            })
            if not success:
                results["remote"]["success"] = False
        
        return results
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get status of all secondary nodes.
        
        Returns:
            Dictionary with status of each node
        """
        status = {
            "docker": [],
            "remote": [],
            "total_nodes": len(self.config.secondaries),
        }
        
        # Check Docker containers
        for node in self.get_docker_nodes():
            node_status = {
                "node_id": node.node_id,
                "container_name": node.container_name,
                "docker_ip": node.docker_ip,
                "host_port": node.port,
                "running": False,
                "reachable": node.is_reachable(),
            }
            
            # Check if container is running
            try:
                result = subprocess.run(
                    ["docker", "inspect", "-f", "{{.State.Running}}", node.container_name],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                node_status["running"] = result.stdout.strip() == "true"
            except Exception:
                pass
            
            status["docker"].append(node_status)
        
        # Check remote nodes
        for node in self.get_remote_nodes():
            status["remote"].append(self.check_remote_node(node))
        
        return status
    
    def scale_docker_nodes(self, target_count: int) -> Tuple[bool, str]:
        """
        Scale Docker secondary nodes to target count.
        
        Args:
            target_count: Target number of Docker secondary nodes
            
        Returns:
            Tuple of (success, message)
        """
        current_docker_nodes = len(self.get_docker_nodes())
        
        if target_count == current_docker_nodes:
            return True, f"Already have {current_docker_nodes} Docker nodes"
        
        if target_count > current_docker_nodes:
            # Add more nodes
            nodes_to_add = target_count - current_docker_nodes
            for _ in range(nodes_to_add):
                self.config.add_secondary(node_type=NodeType.DOCKER_CONTAINER)
        else:
            # Remove nodes (from the end)
            nodes_to_remove = current_docker_nodes - target_count
            docker_nodes = self.get_docker_nodes()
            for _ in range(nodes_to_remove):
                node_to_remove = docker_nodes.pop()
                self.config.secondaries.remove(node_to_remove)
        
        # Regenerate and restart containers
        self.generate_docker_compose()
        success, msg = self.start_docker_containers()
        
        if success:
            return True, f"Scaled to {target_count} Docker nodes"
        return False, msg
    
    def install_lineairdb_plugin_on_docker(
        self,
        node: NodeConfig,
        plugin_path: str,
    ) -> Tuple[bool, str]:
        """
        Install LineairDB storage engine plugin on a Docker container.
        
        Args:
            node: Docker node configuration
            plugin_path: Path to the plugin file on the host
            
        Returns:
            Tuple of (success, message)
        """
        if node.node_type != NodeType.DOCKER_CONTAINER:
            return False, "Node is not a Docker container"
        
        if not os.path.exists(plugin_path):
            return False, f"Plugin file not found: {plugin_path}"
        
        plugin_filename = os.path.basename(plugin_path)
        container_plugin_dir = "/usr/lib/mysql/plugin"
        container_plugin_path = f"{container_plugin_dir}/{plugin_filename}"
        
        try:
            # Copy plugin to container
            logger.info(f"Copying plugin to container {node.container_name}...")
            result = subprocess.run(
                ["docker", "cp", plugin_path, f"{node.container_name}:{container_plugin_path}"],
                capture_output=True,
                text=True,
                timeout=60
            )
            if result.returncode != 0:
                return False, f"Failed to copy plugin: {result.stderr}"
            
            # Set correct permissions
            result = subprocess.run(
                ["docker", "exec", node.container_name, "chmod", "755", container_plugin_path],
                capture_output=True,
                text=True,
                timeout=30
            )
            if result.returncode != 0:
                return False, f"Failed to set plugin permissions: {result.stderr}"
            
            # Install plugin via MySQL
            mysql_cmd = f"mysql -uroot -p{node.mysql_root_password} -e \"INSTALL PLUGIN lineairdb SONAME '{plugin_filename}';\""
            result = subprocess.run(
                ["docker", "exec", node.container_name, "bash", "-c", mysql_cmd],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            # Check if plugin already installed (not an error)
            if result.returncode != 0:
                if "already exists" in result.stderr.lower() or "duplicate" in result.stderr.lower():
                    return True, "LineairDB plugin already installed"
                return False, f"Failed to install plugin: {result.stderr}"
            
            return True, "LineairDB plugin installed successfully"
        
        except subprocess.TimeoutExpired:
            return False, "Timeout installing plugin"
        except Exception as e:
            return False, str(e)
    
    def install_lineairdb_plugin_on_remote(
        self,
        node: NodeConfig,
        plugin_path: str,
        remote_plugin_dir: str = "/usr/lib/mysql/plugin",
    ) -> Tuple[bool, str]:
        """
        Install LineairDB storage engine plugin on a remote machine.
        
        Args:
            node: Remote node configuration
            plugin_path: Path to the plugin file on the local machine
            remote_plugin_dir: Plugin directory on the remote machine
            
        Returns:
            Tuple of (success, message)
        """
        if node.node_type != NodeType.REMOTE_MACHINE:
            return False, "Node is not a remote machine"
        
        if not node.ssh_user:
            return False, "SSH user not configured"
        
        if not os.path.exists(plugin_path):
            return False, f"Plugin file not found: {plugin_path}"
        
        plugin_filename = os.path.basename(plugin_path)
        remote_plugin_path = f"{remote_plugin_dir}/{plugin_filename}"
        
        try:
            # Build SCP command
            scp_cmd = ["scp"]
            if node.ssh_key_path:
                scp_cmd.extend(["-i", node.ssh_key_path])
            scp_cmd.extend([
                "-o", "StrictHostKeyChecking=no",
                "-P", str(node.ssh_port),
                plugin_path,
                f"{node.ssh_user}@{node.host}:/tmp/{plugin_filename}"
            ])
            
            # Copy plugin to remote machine
            logger.info(f"Copying plugin to remote machine {node.host}...")
            result = subprocess.run(
                scp_cmd,
                capture_output=True,
                text=True,
                timeout=120
            )
            if result.returncode != 0:
                return False, f"Failed to copy plugin: {result.stderr}"
            
            # Move plugin to correct directory and set permissions
            success, output = self._run_ssh_command(
                node,
                f"sudo mv /tmp/{plugin_filename} {remote_plugin_path} && sudo chmod 755 {remote_plugin_path}",
                timeout=60
            )
            if not success:
                return False, f"Failed to move plugin: {output}"
            
            # Install plugin via MySQL
            install_cmd = f"mysql -uroot -p{node.mysql_root_password} -e \"INSTALL PLUGIN lineairdb SONAME '{plugin_filename}';\""
            success, output = self._run_ssh_command(node, install_cmd, timeout=30)
            
            # Check if plugin already installed (not an error)
            if not success:
                if "already exists" in output.lower() or "duplicate" in output.lower():
                    return True, "LineairDB plugin already installed"
                return False, f"Failed to install plugin: {output}"
            
            return True, "LineairDB plugin installed successfully"
        
        except subprocess.TimeoutExpired:
            return False, "Timeout installing plugin"
        except Exception as e:
            return False, str(e)
    
    def install_lineairdb_plugin(
        self,
        node: NodeConfig,
        plugin_path: str,
    ) -> Tuple[bool, str]:
        """
        Install LineairDB storage engine plugin on a secondary node.
        
        Automatically detects node type and uses appropriate method.
        
        Args:
            node: Node configuration
            plugin_path: Path to the plugin file
            
        Returns:
            Tuple of (success, message)
        """
        if node.node_type == NodeType.DOCKER_CONTAINER:
            return self.install_lineairdb_plugin_on_docker(node, plugin_path)
        elif node.node_type == NodeType.REMOTE_MACHINE:
            return self.install_lineairdb_plugin_on_remote(node, plugin_path)
        else:
            return False, f"Unsupported node type: {node.node_type}"
    
    def install_lineairdb_plugin_on_all(
        self,
        plugin_path: str,
    ) -> Dict[str, Any]:
        """
        Install LineairDB storage engine plugin on all secondary nodes.
        
        Args:
            plugin_path: Path to the plugin file
            
        Returns:
            Dictionary with installation results for each node
        """
        results = {
            "success": True,
            "nodes": [],
        }
        
        for node in self.config.secondaries:
            logger.info(f"Installing LineairDB plugin on node {node.node_id} ({node.hostname})...")
            success, message = self.install_lineairdb_plugin(node, plugin_path)
            
            node_result = {
                "node_id": node.node_id,
                "hostname": node.hostname,
                "node_type": node.node_type.value,
                "success": success,
                "message": message,
            }
            results["nodes"].append(node_result)
            
            if not success:
                results["success"] = False
                logger.warning(f"Failed to install plugin on node {node.node_id}: {message}")
            else:
                logger.info(f"Successfully installed plugin on node {node.node_id}")
        
        return results
    
    def check_lineairdb_plugin(self, node: NodeConfig) -> Tuple[bool, str]:
        """
        Check if LineairDB plugin is installed on a secondary node.
        
        Args:
            node: Node configuration
            
        Returns:
            Tuple of (available, message)
        """
        check_sql = "SELECT PLUGIN_NAME, PLUGIN_STATUS FROM information_schema.PLUGINS WHERE PLUGIN_NAME='lineairdb';"
        
        if node.node_type == NodeType.DOCKER_CONTAINER:
            try:
                mysql_cmd = f"mysql -uroot -p{node.mysql_root_password} -N -e \"{check_sql}\""
                result = subprocess.run(
                    ["docker", "exec", node.container_name, "bash", "-c", mysql_cmd],
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                if "lineairdb" in result.stdout.lower():
                    return True, "LineairDB plugin is available"
                return False, "LineairDB plugin is not installed"
            except Exception as e:
                return False, str(e)
        
        elif node.node_type == NodeType.REMOTE_MACHINE:
            check_cmd = f"mysql -uroot -p{node.mysql_root_password} -N -e \"{check_sql}\""
            success, output = self._run_ssh_command(node, check_cmd, timeout=30)
            if success and "lineairdb" in output.lower():
                return True, "LineairDB plugin is available"
            return False, "LineairDB plugin is not installed"
        
        return False, f"Unsupported node type: {node.node_type}"


def create_secondary_nodes(
    count: int,
    remote_hosts: Optional[List[Dict[str, str]]] = None,
    config: Optional[ClusterConfig] = None,
) -> List[NodeConfig]:
    """
    Create secondary node configurations.
    
    Uses remote machines if provided, falls back to Docker containers.
    
    Args:
        count: Total number of secondary nodes
        remote_hosts: Optional list of remote host configurations
        config: Optional cluster configuration to add nodes to
    
    Returns:
        List of created NodeConfig instances
    """
    if config is None:
        from .config import ClusterConfig
        config = ClusterConfig()
    
    return config.add_multiple_secondaries(count, remote_hosts)

