#!/usr/bin/env python3
"""
Example: LineairDB Storage Engine Integration with MySQL Cluster Bridge

This example shows how to use the MySQL Cluster Bridge from within
the LineairDB storage engine replication module.

Place this in: LineairDB-storage-engine/repl/
"""

import sys
from pathlib import Path

# Add the cluster submodule to the path
# Assuming mysql-cluster is a submodule at LineairDB-storage-engine/cluster/
CLUSTER_PATH = Path(__file__).parent.parent / "cluster"
sys.path.insert(0, str(CLUSTER_PATH))

from bridge import ClusterBridge, create_cluster, load_cluster
from bridge.config import NodeType


def setup_cluster_for_lineairdb():
    """
    Set up a MySQL cluster optimized for LineairDB storage engine.
    
    This function creates a cluster with:
    - Local primary node (where LineairDB runs)
    - Configurable secondary nodes
    """
    
    # Example 1: Simple setup with Docker secondaries
    print("Setting up cluster with Docker secondaries...")
    cluster = create_cluster(num_secondaries=3)
    cluster.start()
    
    return cluster


def setup_distributed_cluster(remote_hosts: list):
    """
    Set up a distributed MySQL cluster with remote machines.
    
    Args:
        remote_hosts: List of remote host configurations
            [{"host": "192.168.1.10", "ssh_user": "mysql", "ssh_key_path": "/path/to/key"}]
    """
    
    print(f"Setting up distributed cluster with {len(remote_hosts)} remote hosts...")
    cluster = create_cluster(
        num_secondaries=len(remote_hosts),
        remote_hosts=remote_hosts,
    )
    cluster.start()
    
    return cluster


def scale_cluster_example():
    """
    Example of scaling the cluster dynamically.
    """
    
    # Load existing cluster
    cluster = load_cluster()
    
    # Get current status
    status = cluster.get_status()
    current_count = len(status["secondaries"]["docker"]) + len(status["secondaries"]["remote"])
    print(f"Current secondary nodes: {current_count}")
    
    # Scale up to 10 nodes
    print("Scaling to 10 secondary nodes...")
    result = cluster.scale(10)
    
    if result["success"]:
        print(f"Scaled from {result['previous_count']} to {result['current_count']} nodes")
    else:
        print(f"Failed to scale: {result['message']}")
    
    return cluster


class LineairDBReplicationManager:
    """
    Example class for managing LineairDB replication using the cluster bridge.
    
    This would be integrated into LineairDB-storage-engine/repl/
    """
    
    def __init__(self, cluster: ClusterBridge = None):
        """
        Initialize the replication manager.
        
        Args:
            cluster: Existing ClusterBridge instance, or None to load from config
        """
        if cluster is None:
            try:
                self.cluster = load_cluster()
            except FileNotFoundError:
                print("No cluster configuration found. Creating new cluster...")
                self.cluster = create_cluster(num_secondaries=2)
        else:
            self.cluster = cluster
    
    def ensure_cluster_running(self) -> bool:
        """
        Ensure the cluster is running and healthy.
        
        Returns:
            True if cluster is running, False otherwise
        """
        status = self.cluster.get_status()
        
        if not status["primary"]["running"]:
            print("Primary node not running. Starting...")
            result = self.cluster.start(setup_replication=False)
            return result["success"]
        
        return True
    
    def get_primary_connection(self) -> dict:
        """
        Get connection details for the primary node.
        
        Returns:
            Dictionary with connection details
        """
        primary = self.cluster.config.primary
        return {
            "host": primary.host,
            "port": primary.port,
            "user": "root",
            "password": primary.mysql_root_password,
        }
    
    def get_secondary_connections(self) -> list:
        """
        Get connection details for all secondary nodes.
        
        Returns:
            List of dictionaries with connection details
        """
        connections = []
        for node in self.cluster.config.secondaries:
            if node.is_reachable():
                connections.append({
                    "node_id": node.node_id,
                    "host": node.host,
                    "port": node.port,
                    "user": "root",
                    "password": node.mysql_root_password,
                })
        return connections
    
    def verify_lineairdb_on_all_nodes(self) -> dict:
        """
        Verify LineairDB storage engine is available on all nodes.
        
        Returns:
            Dictionary with availability status for each node
        """
        return self.cluster.check_lineairdb()
    
    def replicate_to_secondaries(self, data: bytes, table_name: str) -> dict:
        """
        Placeholder for LineairDB replication logic.
        
        This would be implemented in the actual LineairDB replication module.
        
        Args:
            data: Data to replicate
            table_name: Target table name
            
        Returns:
            Dictionary with replication results
        """
        # This is a placeholder - actual implementation would:
        # 1. Convert LineairDB data format
        # 2. Generate SQL statements
        # 3. Execute on primary (which replicates to secondaries via group replication)
        
        results = {
            "success": True,
            "nodes_replicated": [],
        }
        
        # The beauty of group replication is that we only need to write to primary
        # MySQL handles the replication automatically
        
        return results


def main():
    """
    Main example function.
    """
    print("=" * 60)
    print("LineairDB Storage Engine - Cluster Bridge Integration")
    print("=" * 60)
    print()
    
    # Check if cluster exists
    config_path = Path.cwd() / "config" / "cluster.json"
    
    if config_path.exists():
        print("Loading existing cluster configuration...")
        manager = LineairDBReplicationManager()
    else:
        print("Creating new cluster with 3 Docker secondary nodes...")
        cluster = create_cluster(num_secondaries=3)
        manager = LineairDBReplicationManager(cluster)
    
    # Ensure cluster is running
    print("\nEnsuring cluster is running...")
    if manager.ensure_cluster_running():
        print("✓ Cluster is running")
    else:
        print("✗ Failed to start cluster")
        return 1
    
    # Get connection info
    print("\nPrimary connection:")
    primary = manager.get_primary_connection()
    print(f"  Host: {primary['host']}:{primary['port']}")
    
    print("\nSecondary connections:")
    for sec in manager.get_secondary_connections():
        print(f"  Node {sec['node_id']}: {sec['host']}:{sec['port']}")
    
    # Check LineairDB availability
    print("\nLineairDB availability:")
    lineairdb_status = manager.verify_lineairdb_on_all_nodes()
    
    primary_available = lineairdb_status.get("primary", {}).get("available", False)
    print(f"  Primary: {'✓' if primary_available else '✗'}")
    
    for sec in lineairdb_status.get("secondaries", []):
        available = sec.get("available", False)
        print(f"  Secondary {sec['node_id']}: {'✓' if available else '✗'}")
    
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())

