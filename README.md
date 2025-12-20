# MySQL Cluster Bridge for LineairDB Storage Engine

A bridge interface for MySQL Group Replication that supports a local primary node (running LineairDB storage engine) with flexible secondary nodes (remote machines or Docker containers).

This repository is designed to be used as a submodule of [LineairDB-storage-engine](https://github.com/Tatzhiro/LineairDB-storage-engine) for distributed group replication.

## Overview

The MySQL Cluster Bridge provides:

- **Primary Node**: Local MySQL installation (via systemctl or binary) where LineairDB storage engine runs
- **Secondary Nodes**: Flexible deployment options:
  - Remote machines (if IP addresses are provided)
  - Docker containers (automatically created if remote machines not available)
- **Auto-scaling**: Create any number of secondary nodes (e.g., 100 Docker containers)
- **Plugin Installation**: Automatically install LineairDB storage engine plugin on all nodes
- **Bridge Interface**: Clean abstraction for LineairDB replication integration

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        LineairDB Storage Engine                       │
│                    (LineairDB-storage-engine/repl)                    │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      MySQL Cluster Bridge                            │
│                    (this repository)                                 │
└─────────────────────────────────────────────────────────────────────┘
                                    │
            ┌───────────────────────┼───────────────────────┐
            ▼                       ▼                       ▼
    ┌───────────────┐       ┌───────────────┐       ┌───────────────┐
    │   Primary     │       │  Secondary    │       │  Secondary    │
    │   (Local)     │◄─────►│  (Remote or   │◄─────►│  (Docker)     │
    │   MySQL +     │       │   Docker)     │       │               │
    │   LineairDB   │       └───────────────┘       └───────────────┘
    └───────────────┘
         │
         ▼
    systemctl or
    binary MySQL
```

## Quick Start

### Prerequisites

- Python 3.8+
- MySQL 8.0.43+ (installed locally via systemctl or binary)
- MySQL Shell (mysqlsh)
- Docker and Docker Compose (for container secondaries)

### Installation

```bash
# Clone the repository
git clone https://github.com/your-repo/mysql-cluster.git
cd mysql-cluster

# Install dependencies
pip install -r requirements.txt
```

### Create a Cluster

#### With Docker Secondaries (Easiest)

```bash
# Create a cluster with 5 Docker secondary nodes
./setup_bridge.py --secondaries 5 --start
```

#### With Remote Machines

```bash
# Create a cluster with remote machines
./setup_bridge.py --secondaries 3 \
    --remote-host 192.168.1.10:mysql \
    --remote-host 192.168.1.11:mysql \
    --start

# Note: If fewer remote hosts are provided than secondaries,
# remaining nodes will be Docker containers
```

#### With Local Binary MySQL

```bash
# Use a custom MySQL binary installation
./setup_bridge.py --secondaries 2 \
    --primary-type binary \
    --mysql-bin-dir /opt/mysql/bin \
    --start
```

### CLI Commands

```bash
# Create cluster configuration
python -m bridge.cli create --secondaries 5

# Set up infrastructure
python -m bridge.cli setup

# Start the cluster
python -m bridge.cli start

# Check cluster status
python -m bridge.cli status
python -m bridge.cli status --json  # JSON output

# Scale secondary nodes
python -m bridge.cli scale 10

# Add a remote secondary
python -m bridge.cli add-secondary 192.168.1.12 --ssh-user mysql

# Remove a secondary node
python -m bridge.cli remove-secondary 3

# Check LineairDB availability
python -m bridge.cli check-lineairdb

# Install LineairDB plugin on all nodes
python -m bridge.cli install-lineairdb
python -m bridge.cli install-lineairdb --plugin-path /path/to/ha_lineairdb.so

# Stop the cluster
python -m bridge.cli stop

# Clean up resources
python -m bridge.cli cleanup --all
```

## Python API

The bridge provides a clean Python API for LineairDB integration:

```python
from bridge import ClusterBridge, create_cluster, load_cluster

# Create a new cluster
cluster = create_cluster(num_secondaries=10)
cluster.start()

# Or with remote machines
cluster = create_cluster(
    num_secondaries=5,
    remote_hosts=[
        {"host": "192.168.1.10", "ssh_user": "mysql"},
        {"host": "192.168.1.11", "ssh_user": "mysql"},
    ]
)
# This creates 2 remote + 3 Docker secondary nodes
cluster.start()

# Load existing cluster
cluster = load_cluster()
status = cluster.get_status()
print(status)

# Scale the cluster
cluster.scale(20)

# Add remote secondary on-the-fly
cluster.add_remote_secondary("192.168.1.12", "mysql")

# Check LineairDB availability
lineairdb_status = cluster.check_lineairdb()

# Install LineairDB plugin on all nodes
# Auto-detects plugin location when used as submodule of LineairDB-storage-engine
cluster.install_lineairdb_plugin()

# Or specify plugin path explicitly
cluster.install_lineairdb_plugin("/path/to/LineairDB-storage-engine/build/ha_lineairdb.so")
```

## Configuration

### Cluster Configuration File

The cluster configuration is stored in `config/cluster.json`:

```json
{
  "cluster_name": "lineairdb_cluster",
  "mysql_version": "8.0.43",
  "mysql_root_password": "kamo",
  "primary": {
    "node_id": 1,
    "hostname": "primary",
    "node_type": "local_systemctl",
    "host": "127.0.0.1",
    "port": 3306
  },
  "secondaries": [
    {
      "node_id": 2,
      "hostname": "mysql-secondary-1",
      "node_type": "docker_container",
      "host": "127.0.0.1",
      "port": 33062,
      "docker_ip": "172.20.0.12"
    }
  ]
}
```

### MySQL Configuration

MySQL configuration files are generated in the `config/` directory:

- `config/primary.cnf` - Primary node configuration
- `config/secondary1.cnf` - Secondary node 1 configuration
- etc.

## Integration with LineairDB-storage-engine

This repository is designed to be used as a submodule:

```bash
cd LineairDB-storage-engine
git submodule add https://github.com/your-repo/mysql-cluster.git cluster

# In your replication code (LineairDB-storage-engine/repl)
from cluster.bridge import ClusterBridge, load_cluster

# Initialize cluster
cluster = load_cluster()

# Use cluster for replication
primary_status = cluster.get_status()["primary"]
if primary_status["running"]:
    # Primary is ready for LineairDB operations
    pass
```

## Node Types

### Primary Node

The primary node runs on the local machine and can be:

1. **LOCAL_SYSTEMCTL**: MySQL managed by systemd
   - Uses `sudo systemctl start/stop mysql`
   - Requires MySQL to be installed via package manager

2. **LOCAL_BINARY**: MySQL from binary installation
   - Uses direct mysqld invocation
   - Specify `--mysql-bin-dir` for custom installation path

### Secondary Nodes

Secondary nodes can be:

1. **REMOTE_MACHINE**: A remote server with MySQL installed
   - Requires SSH access
   - MySQL must be pre-installed and configured
   - Managed via SSH commands

2. **DOCKER_CONTAINER**: Local Docker container
   - Automatically created and managed
   - Uses official MySQL 8.0.43 image
   - Good for testing and development

## LineairDB Plugin Installation

After cluster creation, you can install the LineairDB storage engine plugin on all nodes:

### Via CLI

```bash
# Auto-detect plugin location (works when this repo is a submodule)
python -m bridge.cli install-lineairdb

# Or specify the plugin path explicitly
python -m bridge.cli install-lineairdb --plugin-path /path/to/ha_lineairdb.so
```

### Via Python API

```python
from bridge import load_cluster

cluster = load_cluster()

# Auto-detect plugin location
result = cluster.install_lineairdb_plugin()

# Or specify explicitly
result = cluster.install_lineairdb_plugin(
    "/path/to/LineairDB-storage-engine/build/ha_lineairdb.so"
)

print(result["summary"])  # e.g., "Installed on 5/5 nodes"
```

### Plugin Auto-Detection

When used as a submodule of LineairDB-storage-engine, the bridge automatically searches for the plugin in:

1. `../build/ha_lineairdb.so` (parent directory build folder)
2. `../build/Release/ha_lineairdb.so`
3. `../build/Debug/ha_lineairdb.so`
4. `../plugins/ha_lineairdb.so`
5. System MySQL plugin directories

### What the Installation Does

1. **For Primary Node**: Copies the plugin to `/usr/lib/mysql/plugin/` and runs `INSTALL PLUGIN`
2. **For Docker Containers**: Uses `docker cp` to copy the plugin and installs via MySQL
3. **For Remote Machines**: Uses `scp` to copy and SSH to install via MySQL

## Scaling

```python
# Scale to 100 secondary nodes
cluster.scale(100)

# Most will be Docker containers unless remote hosts are configured
```

When scaling:
- Remote machine nodes are preserved
- Docker containers are added/removed as needed
- New nodes are automatically added to the InnoDB cluster

## File Structure

```
mysql-cluster/
├── bridge/                     # Python bridge module
│   ├── __init__.py
│   ├── config.py              # Configuration management
│   ├── primary.py             # Primary node manager
│   ├── secondary.py           # Secondary node manager
│   ├── cluster.py             # Main bridge interface
│   └── cli.py                 # Command-line interface
├── examples/                   # Integration examples
│   └── lineairdb_integration.py
├── config/                     # Generated configuration files (created at runtime)
│   ├── cluster.json           # Cluster configuration
│   ├── primary.cnf            # Primary MySQL config
│   └── secondary*.cnf         # Secondary MySQL configs
├── data/                       # Data directories (created at runtime)
│   ├── primary/               # Primary node data
│   └── secondary*/            # Secondary node data
├── logs/                       # Log files (created at runtime)
├── setup_bridge.py            # Setup script
├── requirements.txt           # Python dependencies
└── README.md                  # This file
```

## Connection Information

### Default Credentials

| Setting | Value |
|---------|-------|
| Root Password | `kamo` |
| Cluster Name | `lineairdb_cluster` |
| Database | `testdb` |
| User | `clusteruser` |
| Password | `kamo` |

**⚠️ WARNING**: Change these passwords in production!

### Connection Strings

**Primary (Local)**:
```bash
mysql -h 127.0.0.1 -P 3306 -u root -pkamo
```

**Secondary (Docker)**:
```bash
# Secondary 1
mysql -h 127.0.0.1 -P 33062 -u root -pkamo

# Secondary 2
mysql -h 127.0.0.1 -P 33063 -u root -pkamo
```

## Troubleshooting

### Primary Node Won't Start

1. Check if MySQL is installed: `which mysqld`
2. Check systemctl status: `sudo systemctl status mysql`
3. Check MySQL error log: `/var/log/mysql/error.log`

### Docker Containers Won't Start

1. Check Docker is running: `docker ps`
2. Check Docker logs: `docker logs mysql-secondary-1`
3. Check available disk space: `df -h`

### Group Replication Issues

1. Ensure all nodes can communicate
2. Check MySQL Shell is installed: `mysqlsh --version`
3. Verify cluster status:
   ```bash
   mysqlsh root:kamo@127.0.0.1:3306 --js -e "dba.getCluster().status()"
   ```

### SSH Access for Remote Nodes

1. Verify SSH connectivity: `ssh user@host echo ok`
2. Check SSH key permissions: `chmod 600 /path/to/key`
3. Ensure MySQL is installed on remote machine

## License

This project is provided as-is for testing and development purposes.

## References

- [LineairDB Storage Engine](https://github.com/Tatzhiro/LineairDB-storage-engine)
- [MySQL Group Replication](https://dev.mysql.com/doc/refman/8.0/en/group-replication.html)
- [MySQL Shell](https://dev.mysql.com/doc/mysql-shell/8.0/en/)
