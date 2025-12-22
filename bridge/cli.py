#!/usr/bin/env python3
"""
Command-line interface for MySQL Cluster Bridge.

Provides commands for managing MySQL clusters with LineairDB storage engine.
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

from .config import ClusterConfig, NodeType, create_default_config
from .cluster import ClusterBridge, create_cluster, load_cluster


def main():
    """Main entry point for CLI."""
    parser = argparse.ArgumentParser(
        description="MySQL Cluster Bridge for LineairDB Storage Engine",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Create a cluster with 5 Docker secondary nodes
  mysql-cluster-bridge create --secondaries 5
  
  # Create a cluster with remote machines
  mysql-cluster-bridge create --secondaries 3 \\
    --remote-host 192.168.1.10:mysql \\
    --remote-host 192.168.1.11:mysql
  
  # Start the cluster
  mysql-cluster-bridge start
  
  # Check cluster status
  mysql-cluster-bridge status
  
  # Scale to 10 secondary nodes
  mysql-cluster-bridge scale 10
  
  # Stop the cluster
  mysql-cluster-bridge stop
"""
    )
    
    parser.add_argument(
        "--config", "-c",
        type=Path,
        default=None,
        help="Path to cluster configuration file"
    )
    
    parser.add_argument(
        "--base-dir", "-d",
        type=Path,
        default=Path.cwd(),
        help="Base directory for cluster files"
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # Create command
    create_parser = subparsers.add_parser("create", help="Create a new cluster configuration")
    create_parser.add_argument(
        "--secondaries", "-n",
        type=int,
        default=2,
        help="Number of secondary nodes (default: 2)"
    )
    create_parser.add_argument(
        "--cluster-name",
        type=str,
        default="lineairdb_cluster",
        help="Name of the cluster (default: lineairdb_cluster)"
    )
    create_parser.add_argument(
        "--primary-type",
        choices=["systemctl", "binary"],
        default="systemctl",
        help="Type of primary node (default: systemctl)"
    )
    create_parser.add_argument(
        "--remote-host",
        action="append",
        dest="remote_hosts",
        metavar="HOST:USER[:KEY]",
        help="Remote host in format host:ssh_user[:ssh_key_path]"
    )
    create_parser.add_argument(
        "--mysql-password",
        type=str,
        default="kamo",
        help="MySQL root password (default: kamo)"
    )
    create_parser.add_argument(
        "--use-official-image",
        action="store_true",
        help="Use official MySQL image instead of custom Ubuntu image"
    )
    create_parser.add_argument(
        "--docker-image",
        type=str,
        default=None,
        help="Custom Docker image tag (default: mysql-lineairdb-ubuntu:8.0.43)"
    )
    
    # Setup command
    setup_parser = subparsers.add_parser("setup", help="Set up cluster infrastructure")
    
    # Start command
    start_parser = subparsers.add_parser("start", help="Start the cluster")
    start_parser.add_argument(
        "--no-replication",
        action="store_true",
        help="Don't set up group replication"
    )
    
    # Stop command
    stop_parser = subparsers.add_parser("stop", help="Stop the cluster")
    
    # Restart command
    restart_parser = subparsers.add_parser("restart", help="Restart the cluster")
    
    # Status command
    status_parser = subparsers.add_parser("status", help="Show cluster status")
    status_parser.add_argument(
        "--json",
        action="store_true",
        help="Output in JSON format"
    )
    
    # Scale command
    scale_parser = subparsers.add_parser("scale", help="Scale secondary nodes")
    scale_parser.add_argument(
        "count",
        type=int,
        help="Target number of secondary nodes"
    )
    
    # Add-secondary command
    add_parser = subparsers.add_parser("add-secondary", help="Add a remote secondary node")
    add_parser.add_argument("host", help="Remote host address")
    add_parser.add_argument("--ssh-user", "-u", required=True, help="SSH user")
    add_parser.add_argument("--ssh-key", "-k", help="Path to SSH key")
    
    # Remove-secondary command
    remove_parser = subparsers.add_parser("remove-secondary", help="Remove a secondary node")
    remove_parser.add_argument("node_id", type=int, help="Node ID to remove")
    
    # Check-lineairdb command
    check_parser = subparsers.add_parser("check-lineairdb", help="Check LineairDB availability")
    
    # Install-lineairdb command
    install_parser = subparsers.add_parser("install-lineairdb", help="Install LineairDB plugin on all nodes")
    install_parser.add_argument(
        "--plugin-path", "-p",
        type=str,
        default=None,
        help="Path to LineairDB plugin file (auto-detected if not provided)"
    )
    
    # Cleanup command
    cleanup_parser = subparsers.add_parser("cleanup", help="Clean up cluster resources")
    cleanup_parser.add_argument(
        "--all",
        action="store_true",
        help="Remove all data and containers"
    )
    cleanup_parser.add_argument(
        "--containers-only",
        action="store_true",
        help="Remove containers only, keep data"
    )
    
    # Build-image command
    build_image_parser = subparsers.add_parser(
        "build-image",
        help="Build the custom Ubuntu-based MySQL Docker image"
    )
    build_image_parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Build without using Docker cache"
    )
    build_image_parser.add_argument(
        "--tag",
        type=str,
        default=None,
        help="Custom image tag (default: mysql-lineairdb-ubuntu:8.0.43)"
    )
    
    # Check-image command
    check_image_parser = subparsers.add_parser(
        "check-image",
        help="Check if the Docker image is available"
    )
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    try:
        return run_command(args)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def run_command(args) -> int:
    """Run the specified command."""
    
    config_path = args.config
    if config_path is None:
        config_path = args.base_dir / "config" / "cluster.json"
    
    if args.command == "create":
        return cmd_create(args)
    
    # build-image doesn't require an existing config
    if args.command == "build-image":
        return cmd_build_image(args)
    
    # Load existing configuration for other commands
    if config_path.exists():
        bridge = load_cluster(config_path)
    else:
        print(f"Configuration not found at {config_path}")
        print("Run 'mysql-cluster-bridge create' first")
        return 1
    
    if args.command == "setup":
        return cmd_setup(bridge)
    elif args.command == "start":
        return cmd_start(bridge, not args.no_replication)
    elif args.command == "stop":
        return cmd_stop(bridge)
    elif args.command == "restart":
        return cmd_restart(bridge)
    elif args.command == "status":
        return cmd_status(bridge, args.json)
    elif args.command == "scale":
        return cmd_scale(bridge, args.count)
    elif args.command == "add-secondary":
        return cmd_add_secondary(bridge, args.host, args.ssh_user, args.ssh_key)
    elif args.command == "remove-secondary":
        return cmd_remove_secondary(bridge, args.node_id)
    elif args.command == "check-lineairdb":
        return cmd_check_lineairdb(bridge)
    elif args.command == "install-lineairdb":
        return cmd_install_lineairdb(bridge, args.plugin_path)
    elif args.command == "cleanup":
        return cmd_cleanup(bridge, args.all, args.containers_only)
    elif args.command == "check-image":
        return cmd_check_image(bridge)
    
    return 0


def cmd_create(args) -> int:
    """Create a new cluster configuration."""
    print("Creating cluster configuration...")
    
    # Parse remote hosts
    remote_hosts = []
    if args.remote_hosts:
        for rh in args.remote_hosts:
            parts = rh.split(":")
            if len(parts) < 2:
                print(f"Invalid remote host format: {rh}")
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
    
    # Determine whether to use custom or official image
    use_custom_image = not args.use_official_image
    
    # Create configuration
    config = create_default_config(
        num_secondaries=args.secondaries,
        primary_type=primary_type,
        remote_hosts=remote_hosts if remote_hosts else None,
        base_dir=args.base_dir,
        use_custom_image=use_custom_image,
    )
    config.cluster_name = args.cluster_name
    config.mysql_root_password = args.mysql_password
    
    # Override docker image if specified
    if args.docker_image:
        config.docker_image = args.docker_image
    
    # Create bridge and set up
    bridge = ClusterBridge(config)
    results = bridge.setup()
    
    if results["success"]:
        print(f"✓ Cluster configuration created successfully")
        print(f"  Config file: {bridge.config.config_dir / 'cluster.json'}")
        print(f"  Primary: {config.primary.node_type.value}")
        print(f"  Secondaries: {len(config.secondaries)}")
        
        docker_count = len([n for n in config.secondaries if n.node_type == NodeType.DOCKER_CONTAINER])
        remote_count = len([n for n in config.secondaries if n.node_type == NodeType.REMOTE_MACHINE])
        
        if docker_count:
            print(f"    - Docker containers: {docker_count}")
            docker_image = config.get_docker_image()
            print(f"    - Docker image: {docker_image}")
            if config.use_custom_image:
                print(f"    - Image type: Custom Ubuntu-based")
            else:
                print(f"    - Image type: Official MySQL (Oracle Linux)")
        if remote_count:
            print(f"    - Remote machines: {remote_count}")
        
        print("\nNext steps:")
        if docker_count and config.use_custom_image:
            # Check if custom image exists
            image_check = bridge.check_docker_image()
            if not image_check["exists"]:
                print("  1. Build the Docker image: mysql-cluster-bridge build-image")
                print("  2. Start the cluster: mysql-cluster-bridge start")
                print("  3. Check status: mysql-cluster-bridge status")
            else:
                print("  1. Start the cluster: mysql-cluster-bridge start")
                print("  2. Check status: mysql-cluster-bridge status")
        else:
            print("  1. Start the cluster: mysql-cluster-bridge start")
            print("  2. Check status: mysql-cluster-bridge status")
        return 0
    else:
        print("✗ Failed to create cluster configuration")
        for step in results.get("steps", []):
            if not step.get("success"):
                print(f"  - {step['name']}: {step.get('error', 'Unknown error')}")
        return 1


def cmd_setup(bridge: ClusterBridge) -> int:
    """Set up cluster infrastructure."""
    print("Setting up cluster infrastructure...")
    
    results = bridge.setup()
    
    if results["success"]:
        print("✓ Cluster infrastructure set up successfully")
        return 0
    else:
        print("✗ Failed to set up cluster infrastructure")
        for step in results.get("steps", []):
            if not step.get("success"):
                print(f"  - {step['name']}: {step.get('error', 'Unknown error')}")
        return 1


def cmd_start(bridge: ClusterBridge, setup_replication: bool) -> int:
    """Start the cluster."""
    print("Starting cluster...")
    
    results = bridge.start(setup_replication=setup_replication)
    
    if results["success"]:
        print("✓ Cluster started successfully")
        return 0
    else:
        print("✗ Cluster started with errors")
        
        if results.get("primary") and not results["primary"].get("success"):
            print(f"  - Primary: {results['primary'].get('message')}")
        
        if results.get("secondaries"):
            sec = results["secondaries"]
            if not sec.get("docker", {}).get("success"):
                print(f"  - Docker: {sec['docker'].get('message')}")
            for node in sec.get("remote", {}).get("nodes", []):
                if not node.get("success"):
                    print(f"  - Remote {node['host']}: {node.get('message')}")
        
        return 1


def cmd_stop(bridge: ClusterBridge) -> int:
    """Stop the cluster."""
    print("Stopping cluster...")
    
    results = bridge.stop()
    
    if results["success"]:
        print("✓ Cluster stopped successfully")
        return 0
    else:
        print("✗ Cluster stopped with errors")
        return 1


def cmd_restart(bridge: ClusterBridge) -> int:
    """Restart the cluster."""
    print("Restarting cluster...")
    
    results = bridge.restart()
    
    if results["success"]:
        print("✓ Cluster restarted successfully")
        return 0
    else:
        print("✗ Cluster restarted with errors")
        return 1


def cmd_status(bridge: ClusterBridge, json_output: bool) -> int:
    """Show cluster status."""
    status = bridge.get_status()
    
    if json_output:
        print(json.dumps(status, indent=2, default=str))
    else:
        print(f"Cluster: {status['cluster_name']}")
        print()
        
        # Primary status
        primary = status.get("primary", {})
        running = "✓" if primary.get("running") else "✗"
        reachable = "✓" if primary.get("reachable") else "✗"
        print(f"Primary Node:")
        print(f"  Host: {primary.get('host')}:{primary.get('port')}")
        print(f"  Type: {primary.get('node_type')}")
        print(f"  Running: {running}  Reachable: {reachable}")
        print()
        
        # Secondary status
        secondaries = status.get("secondaries", {})
        docker_nodes = secondaries.get("docker", [])
        remote_nodes = secondaries.get("remote", [])
        
        if docker_nodes:
            print(f"Docker Secondary Nodes ({len(docker_nodes)}):")
            for node in docker_nodes:
                running = "✓" if node.get("running") else "✗"
                reachable = "✓" if node.get("reachable") else "✗"
                print(f"  - {node.get('container_name')}: Running: {running}  Reachable: {reachable}")
            print()
        
        if remote_nodes:
            print(f"Remote Secondary Nodes ({len(remote_nodes)}):")
            for node in remote_nodes:
                reachable = "✓" if node.get("reachable") else "✗"
                mysql_running = "✓" if node.get("mysql_running") else "✗"
                print(f"  - {node.get('host')}: Reachable: {reachable}  MySQL: {mysql_running}")
            print()
        
        # Cluster status
        cluster = status.get("cluster")
        if cluster:
            print("InnoDB Cluster Status:")
            if isinstance(cluster, dict):
                print(json.dumps(cluster, indent=2))
            else:
                print(f"  {cluster}")
    
    return 0


def cmd_scale(bridge: ClusterBridge, count: int) -> int:
    """Scale secondary nodes."""
    print(f"Scaling to {count} secondary nodes...")
    
    results = bridge.scale(count)
    
    if results["success"]:
        print(f"✓ Scaled from {results['previous_count']} to {results['current_count']} nodes")
        return 0
    else:
        print(f"✗ Failed to scale: {results.get('message')}")
        return 1


def cmd_add_secondary(bridge: ClusterBridge, host: str, ssh_user: str, ssh_key: Optional[str]) -> int:
    """Add a remote secondary node."""
    print(f"Adding remote secondary node: {host}...")
    
    success, message = bridge.add_remote_secondary(host, ssh_user, ssh_key)
    
    if success:
        print(f"✓ {message}")
        return 0
    else:
        print(f"✗ {message}")
        return 1


def cmd_remove_secondary(bridge: ClusterBridge, node_id: int) -> int:
    """Remove a secondary node."""
    print(f"Removing secondary node {node_id}...")
    
    success, message = bridge.remove_secondary(node_id)
    
    if success:
        print(f"✓ {message}")
        return 0
    else:
        print(f"✗ {message}")
        return 1


def cmd_check_lineairdb(bridge: ClusterBridge) -> int:
    """Check LineairDB availability."""
    print("Checking LineairDB storage engine availability...")
    
    results = bridge.check_lineairdb()
    
    primary = results.get("primary", {})
    available = "✓" if primary.get("available") else "✗"
    print(f"Primary: {available} {primary.get('message')}")
    
    for sec in results.get("secondaries", []):
        available = "✓" if sec.get("available") else "✗"
        print(f"Secondary {sec.get('node_id')}: {available} {sec.get('message')}")
    
    return 0


def cmd_install_lineairdb(bridge: ClusterBridge, plugin_path: Optional[str]) -> int:
    """Install LineairDB plugin on all nodes."""
    print("Installing LineairDB storage engine plugin on all nodes...")
    
    results = bridge.install_lineairdb_plugin(plugin_path)
    
    if results.get("error"):
        print(f"✗ {results['error']}")
        return 1
    
    print(f"Plugin path: {results.get('plugin_path')}")
    print()
    
    # Primary result
    primary = results.get("primary", {})
    status = "✓" if primary.get("success") else "✗"
    print(f"Primary: {status} {primary.get('message')}")
    
    # Secondary results
    sec_results = results.get("secondaries", {})
    for node in sec_results.get("nodes", []):
        status = "✓" if node.get("success") else "✗"
        print(f"Secondary {node.get('node_id')} ({node.get('hostname')}): {status} {node.get('message')}")
    
    print()
    print(results.get("summary", ""))
    
    if results["success"]:
        print("\n✓ LineairDB plugin installed successfully on all nodes")
        return 0
    else:
        print("\n✗ LineairDB plugin installation failed on some nodes")
        return 1


def cmd_cleanup(bridge: ClusterBridge, cleanup_all: bool, containers_only: bool) -> int:
    """Clean up cluster resources."""
    import subprocess
    import shutil
    
    print("Cleaning up cluster resources...")
    
    # Stop the cluster first
    bridge.stop()
    
    # Stop and remove Docker containers
    docker_compose_path = bridge.config.base_dir / "docker-compose-secondaries.yml"
    if docker_compose_path.exists():
        subprocess.run(
            ["docker-compose", "-f", str(docker_compose_path), "down", "-v"],
            capture_output=True,
            cwd=str(bridge.config.base_dir)
        )
    
    if cleanup_all or containers_only:
        # Remove all Docker containers with mysql-secondary prefix
        for node in bridge.secondary_manager.get_docker_nodes():
            subprocess.run(
                ["docker", "rm", "-f", node.container_name],
                capture_output=True
            )
    
    if cleanup_all:
        # Remove data directories
        if bridge.config.data_dir.exists():
            print(f"Removing data directory: {bridge.config.data_dir}")
            shutil.rmtree(bridge.config.data_dir, ignore_errors=True)
        
        # Remove logs
        if bridge.config.logs_dir.exists():
            print(f"Removing logs directory: {bridge.config.logs_dir}")
            shutil.rmtree(bridge.config.logs_dir, ignore_errors=True)
    
    print("✓ Cleanup completed")
    return 0


def cmd_build_image(args) -> int:
    """Build the custom Ubuntu-based MySQL Docker image."""
    import subprocess
    from .config import ClusterConfig
    
    print("Building Ubuntu-based MySQL Docker image...")
    print()
    
    # Create a temporary config to get docker settings
    config = ClusterConfig(
        base_dir=args.base_dir,
        docker_dir=args.base_dir / "docker",
    )
    
    # Override tag if specified
    if args.tag:
        config.docker_image = args.tag
    
    # Check if Dockerfile exists
    dockerfile_path = config.docker_dir / "Dockerfile.ubuntu"
    entrypoint_path = config.docker_dir / "docker-entrypoint.sh"
    
    if not dockerfile_path.exists():
        print(f"✗ Dockerfile not found at {dockerfile_path}")
        print()
        print("Make sure you have the docker/ directory with:")
        print("  - Dockerfile.ubuntu")
        print("  - docker-entrypoint.sh")
        return 1
    
    if not entrypoint_path.exists():
        print(f"✗ Entrypoint script not found at {entrypoint_path}")
        return 1
    
    print(f"Docker directory: {config.docker_dir}")
    print(f"Image tag: {config.docker_image}")
    print(f"No cache: {args.no_cache}")
    print()
    
    # Build the image directly without requiring a full ClusterBridge
    try:
        cmd = [
            "docker", "build",
            "-t", config.docker_image,
            "-f", str(dockerfile_path),
        ]
        
        if args.no_cache:
            cmd.append("--no-cache")
        
        cmd.append(str(config.docker_dir))
        
        print("Running: " + " ".join(cmd))
        print()
        
        result = subprocess.run(cmd, timeout=1200)  # 20 minutes for build
        
        if result.returncode != 0:
            print(f"✗ Build failed with exit code {result.returncode}")
            return 1
        
        print()
        print(f"✓ Successfully built image '{config.docker_image}'")
        
        # Get image size
        inspect_result = subprocess.run(
            ["docker", "image", "inspect", config.docker_image, "--format", "{{.Size}}"],
            capture_output=True,
            text=True,
            timeout=30
        )
        if inspect_result.returncode == 0:
            size_bytes = int(inspect_result.stdout.strip())
            size_mb = size_bytes / (1024 * 1024)
            print(f"  Image size: {size_mb:.2f} MB")
        
        print()
        print("You can now create a cluster with:")
        print("  python3 -m bridge.cli create --secondaries 3")
        return 0
        
    except subprocess.TimeoutExpired:
        print("✗ Build timed out after 20 minutes")
        return 1
    except Exception as e:
        print(f"✗ Build failed: {e}")
        return 1


def cmd_check_image(bridge: ClusterBridge) -> int:
    """Check if the Docker image is available."""
    print("Checking Docker image...")
    print()
    
    result = bridge.check_docker_image()
    
    print(f"Image: {result['image']}")
    print(f"Type: {'Custom Ubuntu' if result['is_custom'] else 'Official MySQL'}")
    
    if result["exists"]:
        print(f"Status: ✓ Available")
        if "created" in result:
            print(f"Created: {result['created']}")
        if "size" in result:
            size_mb = result["size"] / (1024 * 1024)
            print(f"Size: {size_mb:.2f} MB")
    else:
        print(f"Status: ✗ Not found")
        if result.get("is_custom"):
            print()
            print("To build the custom image, run:")
            print("  mysql-cluster-bridge build-image")
    
    return 0 if result["exists"] else 1


if __name__ == "__main__":
    sys.exit(main())

