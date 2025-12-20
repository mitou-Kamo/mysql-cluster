#!/usr/bin/env python3
"""
Configuration management for MySQL Cluster Bridge.

Defines the configuration schema for:
- Primary node (local MySQL via systemctl or binary)
- Secondary nodes (remote machines or Docker containers)
"""

import os
import json
import socket
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from enum import Enum
from pathlib import Path


class NodeType(Enum):
    """Type of MySQL node deployment."""
    LOCAL_SYSTEMCTL = "local_systemctl"  # Local MySQL managed by systemctl
    LOCAL_BINARY = "local_binary"        # Local MySQL from binary installation
    REMOTE_MACHINE = "remote_machine"    # Remote machine with MySQL
    DOCKER_CONTAINER = "docker_container"  # Docker container


class NodeRole(Enum):
    """Role of the node in the cluster."""
    PRIMARY = "primary"
    SECONDARY = "secondary"


@dataclass
class NodeConfig:
    """Configuration for a single MySQL node."""
    
    # Node identification
    node_id: int
    hostname: str
    role: NodeRole
    node_type: NodeType
    
    # Connection details
    host: str = "127.0.0.1"
    port: int = 3306
    mysql_root_password: str = "kamo"
    
    # For remote machines
    ssh_user: Optional[str] = None
    ssh_key_path: Optional[str] = None
    ssh_port: int = 22
    
    # For Docker containers
    container_name: Optional[str] = None
    docker_network: str = "mysql-cluster-net"
    docker_ip: Optional[str] = None
    
    # MySQL configuration
    server_id: Optional[int] = None
    data_dir: Optional[str] = None
    config_file: Optional[str] = None
    
    # Group Replication
    local_address: Optional[str] = None
    group_seeds: Optional[str] = None
    
    def __post_init__(self):
        """Set default values after initialization."""
        if self.server_id is None:
            self.server_id = self.node_id
        if self.container_name is None and self.node_type == NodeType.DOCKER_CONTAINER:
            self.container_name = f"mysql-node-{self.node_id}"
    
    def get_connection_uri(self) -> str:
        """Get MySQL connection URI for MySQL Shell."""
        return f"root:{self.mysql_root_password}@{self.host}:{self.port}"
    
    def get_local_address(self) -> str:
        """Get local address for group replication."""
        if self.local_address:
            return self.local_address
        return f"{self.hostname}:3306"
    
    def is_reachable(self) -> bool:
        """Check if the node is reachable."""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            result = sock.connect_ex((self.host, self.port))
            sock.close()
            return result == 0
        except Exception:
            return False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "node_id": self.node_id,
            "hostname": self.hostname,
            "role": self.role.value,
            "node_type": self.node_type.value,
            "host": self.host,
            "port": self.port,
            "mysql_root_password": self.mysql_root_password,
            "ssh_user": self.ssh_user,
            "ssh_key_path": self.ssh_key_path,
            "ssh_port": self.ssh_port,
            "container_name": self.container_name,
            "docker_network": self.docker_network,
            "docker_ip": self.docker_ip,
            "server_id": self.server_id,
            "data_dir": self.data_dir,
            "config_file": self.config_file,
            "local_address": self.local_address,
            "group_seeds": self.group_seeds,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "NodeConfig":
        """Create from dictionary."""
        data = data.copy()
        data["role"] = NodeRole(data["role"])
        data["node_type"] = NodeType(data["node_type"])
        return cls(**data)


@dataclass
class ClusterConfig:
    """Configuration for the entire MySQL cluster."""
    
    # Cluster identification
    cluster_name: str = "lineairdb_cluster"
    
    # Primary node configuration
    primary: Optional[NodeConfig] = None
    
    # Secondary nodes configuration
    secondaries: List[NodeConfig] = field(default_factory=list)
    
    # Network configuration
    docker_network_name: str = "mysql-cluster-net"
    docker_network_subnet: str = "172.20.0.0/16"
    docker_base_ip: str = "172.20.0"
    
    # MySQL configuration
    mysql_version: str = "8.0.43"
    mysql_root_password: str = "kamo"
    mysql_database: str = "testdb"
    mysql_user: str = "clusteruser"
    mysql_user_password: str = "kamo"
    
    # Paths
    base_dir: Path = field(default_factory=lambda: Path.cwd())
    config_dir: Path = field(default_factory=lambda: Path.cwd() / "config")
    data_dir: Path = field(default_factory=lambda: Path.cwd() / "data")
    logs_dir: Path = field(default_factory=lambda: Path.cwd() / "logs")
    
    # MySQL binary paths (for local binary installation)
    mysql_bin_dir: Optional[str] = None
    mysqld_path: Optional[str] = None
    mysql_client_path: Optional[str] = None
    mysqlsh_path: Optional[str] = None
    
    def __post_init__(self):
        """Initialize paths and set defaults."""
        if isinstance(self.base_dir, str):
            self.base_dir = Path(self.base_dir)
        if isinstance(self.config_dir, str):
            self.config_dir = Path(self.config_dir)
        if isinstance(self.data_dir, str):
            self.data_dir = Path(self.data_dir)
        if isinstance(self.logs_dir, str):
            self.logs_dir = Path(self.logs_dir)
    
    def get_all_nodes(self) -> List[NodeConfig]:
        """Get all nodes (primary + secondaries)."""
        nodes = []
        if self.primary:
            nodes.append(self.primary)
        nodes.extend(self.secondaries)
        return nodes
    
    def get_node_count(self) -> int:
        """Get total number of nodes."""
        count = len(self.secondaries)
        if self.primary:
            count += 1
        return count
    
    def get_group_seeds(self) -> str:
        """Get group replication seeds string."""
        seeds = []
        for node in self.get_all_nodes():
            seeds.append(node.get_local_address())
        return ",".join(seeds)
    
    def add_secondary(
        self,
        host: Optional[str] = None,
        ssh_user: Optional[str] = None,
        ssh_key_path: Optional[str] = None,
        node_type: Optional[NodeType] = None,
    ) -> NodeConfig:
        """
        Add a secondary node to the cluster.
        
        If host is provided and reachable, creates a remote machine node.
        Otherwise, creates a Docker container node.
        """
        node_id = len(self.secondaries) + 2  # Primary is 1
        
        # Determine node type
        if node_type is None:
            if host and ssh_user:
                # Try to reach the remote machine
                node_type = NodeType.REMOTE_MACHINE
            else:
                node_type = NodeType.DOCKER_CONTAINER
        
        if node_type == NodeType.DOCKER_CONTAINER:
            # Create Docker container configuration
            docker_ip = f"{self.docker_base_ip}.{10 + node_id}"
            container_name = f"mysql-secondary-{node_id - 1}"
            
            node = NodeConfig(
                node_id=node_id,
                hostname=container_name,
                role=NodeRole.SECONDARY,
                node_type=NodeType.DOCKER_CONTAINER,
                host="127.0.0.1",
                port=33060 + node_id,
                mysql_root_password=self.mysql_root_password,
                container_name=container_name,
                docker_network=self.docker_network_name,
                docker_ip=docker_ip,
            )
        else:
            # Remote machine configuration
            node = NodeConfig(
                node_id=node_id,
                hostname=host or f"secondary-{node_id - 1}",
                role=NodeRole.SECONDARY,
                node_type=NodeType.REMOTE_MACHINE,
                host=host or "127.0.0.1",
                port=3306,
                mysql_root_password=self.mysql_root_password,
                ssh_user=ssh_user,
                ssh_key_path=ssh_key_path,
            )
        
        self.secondaries.append(node)
        return node
    
    def add_multiple_secondaries(
        self,
        count: int,
        remote_hosts: Optional[List[Dict[str, str]]] = None,
    ) -> List[NodeConfig]:
        """
        Add multiple secondary nodes.
        
        Args:
            count: Total number of secondary nodes to add
            remote_hosts: Optional list of remote host configs:
                [{"host": "192.168.1.10", "ssh_user": "mysql", "ssh_key_path": "/path/to/key"}]
        
        If remote_hosts is provided and available, uses remote machines.
        Remaining nodes are created as Docker containers.
        """
        added_nodes = []
        remote_hosts = remote_hosts or []
        
        for i in range(count):
            if i < len(remote_hosts):
                # Use remote machine
                rh = remote_hosts[i]
                node = self.add_secondary(
                    host=rh.get("host"),
                    ssh_user=rh.get("ssh_user"),
                    ssh_key_path=rh.get("ssh_key_path"),
                    node_type=NodeType.REMOTE_MACHINE,
                )
            else:
                # Use Docker container
                node = self.add_secondary(node_type=NodeType.DOCKER_CONTAINER)
            added_nodes.append(node)
        
        return added_nodes
    
    def save(self, filepath: Optional[Path] = None) -> Path:
        """Save configuration to JSON file."""
        if filepath is None:
            filepath = self.config_dir / "cluster.json"
        
        filepath.parent.mkdir(parents=True, exist_ok=True)
        
        data = {
            "cluster_name": self.cluster_name,
            "mysql_version": self.mysql_version,
            "mysql_root_password": self.mysql_root_password,
            "mysql_database": self.mysql_database,
            "mysql_user": self.mysql_user,
            "mysql_user_password": self.mysql_user_password,
            "docker_network_name": self.docker_network_name,
            "docker_network_subnet": self.docker_network_subnet,
            "docker_base_ip": self.docker_base_ip,
            "base_dir": str(self.base_dir),
            "config_dir": str(self.config_dir),
            "data_dir": str(self.data_dir),
            "logs_dir": str(self.logs_dir),
            "mysql_bin_dir": self.mysql_bin_dir,
            "mysqld_path": self.mysqld_path,
            "mysql_client_path": self.mysql_client_path,
            "mysqlsh_path": self.mysqlsh_path,
            "primary": self.primary.to_dict() if self.primary else None,
            "secondaries": [s.to_dict() for s in self.secondaries],
        }
        
        with open(filepath, "w") as f:
            json.dump(data, f, indent=2)
        
        return filepath
    
    @classmethod
    def load(cls, filepath: Path) -> "ClusterConfig":
        """Load configuration from JSON file."""
        with open(filepath) as f:
            data = json.load(f)
        
        config = cls(
            cluster_name=data.get("cluster_name", "lineairdb_cluster"),
            mysql_version=data.get("mysql_version", "8.0.43"),
            mysql_root_password=data.get("mysql_root_password", "kamo"),
            mysql_database=data.get("mysql_database", "testdb"),
            mysql_user=data.get("mysql_user", "clusteruser"),
            mysql_user_password=data.get("mysql_user_password", "kamo"),
            docker_network_name=data.get("docker_network_name", "mysql-cluster-net"),
            docker_network_subnet=data.get("docker_network_subnet", "172.20.0.0/16"),
            docker_base_ip=data.get("docker_base_ip", "172.20.0"),
            base_dir=Path(data.get("base_dir", ".")),
            config_dir=Path(data.get("config_dir", "./config")),
            data_dir=Path(data.get("data_dir", "./data")),
            logs_dir=Path(data.get("logs_dir", "./logs")),
            mysql_bin_dir=data.get("mysql_bin_dir"),
            mysqld_path=data.get("mysqld_path"),
            mysql_client_path=data.get("mysql_client_path"),
            mysqlsh_path=data.get("mysqlsh_path"),
        )
        
        if data.get("primary"):
            config.primary = NodeConfig.from_dict(data["primary"])
        
        for sec_data in data.get("secondaries", []):
            config.secondaries.append(NodeConfig.from_dict(sec_data))
        
        return config


def create_default_config(
    num_secondaries: int = 2,
    primary_type: NodeType = NodeType.LOCAL_SYSTEMCTL,
    remote_hosts: Optional[List[Dict[str, str]]] = None,
    base_dir: Optional[Path] = None,
) -> ClusterConfig:
    """
    Create a default cluster configuration.
    
    Args:
        num_secondaries: Number of secondary nodes
        primary_type: Type of primary node (LOCAL_SYSTEMCTL or LOCAL_BINARY)
        remote_hosts: Optional list of remote hosts for secondary nodes
        base_dir: Base directory for cluster files
    
    Returns:
        ClusterConfig instance
    """
    base_dir = base_dir or Path.cwd()
    
    config = ClusterConfig(
        base_dir=base_dir,
        config_dir=base_dir / "config",
        data_dir=base_dir / "data",
        logs_dir=base_dir / "logs",
    )
    
    # Configure primary node (local MySQL)
    config.primary = NodeConfig(
        node_id=1,
        hostname=socket.gethostname(),
        role=NodeRole.PRIMARY,
        node_type=primary_type,
        host="127.0.0.1",
        port=3306,
        mysql_root_password=config.mysql_root_password,
        server_id=1,
        data_dir=str(base_dir / "data" / "primary") if primary_type == NodeType.LOCAL_BINARY else None,
    )
    
    # Add secondary nodes
    config.add_multiple_secondaries(num_secondaries, remote_hosts)
    
    return config

