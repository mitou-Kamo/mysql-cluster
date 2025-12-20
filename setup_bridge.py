#!/usr/bin/env python3
"""
Setup script for MySQL Cluster Bridge.

This is the main entry point for setting up a MySQL cluster
with LineairDB storage engine support.

Usage:
    # Create a cluster with Docker secondaries
    ./setup_bridge.py --secondaries 5
    
    # Create a cluster with remote machines
    ./setup_bridge.py --secondaries 3 \
        --remote-host 192.168.1.10:mysql \
        --remote-host 192.168.1.11:mysql
    
    # Use local binary MySQL instead of systemctl
    ./setup_bridge.py --primary-type binary --mysql-bin-dir /opt/mysql/bin
"""

import argparse
import sys
from pathlib import Path

# Add the bridge module to path
sys.path.insert(0, str(Path(__file__).parent))

from bridge.config import ClusterConfig, NodeType, create_default_config
from bridge.cluster import ClusterBridge


def main():
    parser = argparse.ArgumentParser(
        description="Set up MySQL Cluster Bridge for LineairDB Storage Engine"
    )
    
    parser.add_argument(
        "--secondaries", "-n",
        type=int,
        default=2,
        help="Number of secondary nodes (default: 2)"
    )
    
    parser.add_argument(
        "--cluster-name",
        type=str,
        default="lineairdb_cluster",
        help="Name of the cluster (default: lineairdb_cluster)"
    )
    
    parser.add_argument(
        "--primary-type",
        choices=["systemctl", "binary"],
        default="systemctl",
        help="Type of primary node (default: systemctl)"
    )
    
    parser.add_argument(
        "--remote-host",
        action="append",
        dest="remote_hosts",
        metavar="HOST:USER[:KEY]",
        help="Remote host in format host:ssh_user[:ssh_key_path]"
    )
    
    parser.add_argument(
        "--mysql-password",
        type=str,
        default="kamo",
        help="MySQL root password (default: kamo)"
    )
    
    parser.add_argument(
        "--mysql-bin-dir",
        type=str,
        default=None,
        help="Path to MySQL binary directory (for binary primary type)"
    )
    
    parser.add_argument(
        "--base-dir",
        type=Path,
        default=Path(__file__).parent,
        help="Base directory for cluster files"
    )
    
    parser.add_argument(
        "--start",
        action="store_true",
        help="Start the cluster after setup"
    )
    
    parser.add_argument(
        "--no-replication",
        action="store_true",
        help="Don't set up group replication (requires --start)"
    )
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("MySQL Cluster Bridge Setup")
    print("For LineairDB Storage Engine")
    print("=" * 60)
    print()
    
    # Parse remote hosts
    remote_hosts = []
    if args.remote_hosts:
        for rh in args.remote_hosts:
            parts = rh.split(":")
            if len(parts) < 2:
                print(f"Error: Invalid remote host format: {rh}")
                print("Expected format: host:ssh_user[:ssh_key_path]")
                return 1
            
            host_config = {
                "host": parts[0],
                "ssh_user": parts[1],
            }
            if len(parts) > 2:
                host_config["ssh_key_path"] = parts[2]
            remote_hosts.append(host_config)
    
    # Determine primary type
    primary_type = NodeType.LOCAL_SYSTEMCTL
    if args.primary_type == "binary":
        primary_type = NodeType.LOCAL_BINARY
    
    print(f"Configuration:")
    print(f"  Cluster Name: {args.cluster_name}")
    print(f"  Primary Type: {args.primary_type}")
    print(f"  Secondary Nodes: {args.secondaries}")
    if remote_hosts:
        print(f"    Remote Machines: {len(remote_hosts)}")
        docker_count = args.secondaries - len(remote_hosts)
        if docker_count > 0:
            print(f"    Docker Containers: {docker_count}")
    else:
        print(f"    Docker Containers: {args.secondaries}")
    print()
    
    # Create configuration
    print("Creating cluster configuration...")
    config = create_default_config(
        num_secondaries=args.secondaries,
        primary_type=primary_type,
        remote_hosts=remote_hosts if remote_hosts else None,
        base_dir=args.base_dir,
    )
    config.cluster_name = args.cluster_name
    config.mysql_root_password = args.mysql_password
    
    if args.mysql_bin_dir:
        config.mysql_bin_dir = args.mysql_bin_dir
    
    # Create bridge
    bridge = ClusterBridge(config)
    
    # Set up infrastructure
    print("Setting up cluster infrastructure...")
    results = bridge.setup()
    
    if not results["success"]:
        print("✗ Failed to set up cluster infrastructure")
        for step in results.get("steps", []):
            if not step.get("success"):
                print(f"  - {step['name']}: {step.get('error', 'Unknown error')}")
        return 1
    
    print("✓ Cluster infrastructure created")
    print(f"  Config file: {bridge.config.config_dir / 'cluster.json'}")
    print()
    
    # Start cluster if requested
    if args.start:
        print("Starting cluster...")
        start_results = bridge.start(setup_replication=not args.no_replication)
        
        if start_results["success"]:
            print("✓ Cluster started successfully")
        else:
            print("✗ Cluster started with errors")
            if start_results.get("primary") and not start_results["primary"].get("success"):
                print(f"  - Primary: {start_results['primary'].get('message')}")
            return 1
    
    print()
    print("=" * 60)
    print("Setup Complete!")
    print("=" * 60)
    print()
    print("Next steps:")
    if not args.start:
        print("  1. Start the cluster:")
        print("     python -m bridge.cli start")
        print()
    print("  2. Check cluster status:")
    print("     python -m bridge.cli status")
    print()
    print("  3. Scale secondary nodes:")
    print("     python -m bridge.cli scale <count>")
    print()
    print("For LineairDB integration, import the bridge module:")
    print("  from bridge import ClusterBridge, load_cluster")
    print("  cluster = load_cluster()")
    print()
    
    return 0


if __name__ == "__main__":
    sys.exit(main())

