# MySQL Cluster with LineairDB Storage Engine

This repository contains a complete setup for a MySQL 8.0.43 cluster with 4 nodes (1 primary, 2 secondary, 1 router) using Docker containers. The cluster is configured to support switching from InnoDB to LineairDB storage engine for performance testing.

## System Requirements

- **OS**: Linux (Ubuntu 20.04+ recommended)
- **Docker**: Version 20.10+
- **Docker Compose**: Version 1.25+
- **MySQL Shell**: Version 8.0.43 (required for cluster setup)
- **Disk Space**: Minimum 10GB free space
- **Memory**: Minimum 4GB RAM (8GB+ recommended)

### Docker Permissions

If you encounter permission errors with Docker, you may need to:
1. Add your user to the docker group: `sudo usermod -aG docker $USER`
2. Log out and log back in, or run: `newgrp docker`
3. Alternatively, use `sudo` with docker commands

## Architecture

The cluster consists of:

1. **Primary Node** (mysql-primary)
   - Port: 33061
   - IP: 172.20.0.10
   - Role: Primary/Write node

2. **Secondary Node 1** (mysql-secondary-1)
   - Port: 33062
   - IP: 172.20.0.11
   - Role: Secondary/Read replica

3. **Secondary Node 2** (mysql-secondary-2)
   - Port: 33063
   - IP: 172.20.0.12
   - Role: Secondary/Read replica

4. **Router Node** (mysql-router)
   - Read/Write Port: 6446
   - Read-Only Port: 6447
   - X Protocol RW: 6448
   - X Protocol RO: 6449
   - IP: 172.20.0.20
   - Role: Load balancer and connection router

## Quick Start

### 1. Check Environment

```bash
./check-environment.sh
```

This will verify:
- System information
- Disk space and memory
- Docker and Docker Compose installation
- Port availability
- Required directories and files

### 2. Run Setup Script

```bash
./setup.sh
```

This script will:
- Check prerequisites (Docker, Docker Compose, MySQL Shell)
- Create necessary directories
- Pull MySQL 8.0.32 and MySQL Router images
- Start all containers
- Set up the InnoDB Cluster using MySQL Shell's `dba.configureInstance()` and `cluster.addInstance()`

### 3. Verify Cluster Status

```bash
./check-cluster-status.sh
```

Or manually check:

```bash
docker exec -it mysql-primary mysql -uroot -pkamo -e "SELECT * FROM performance_schema.replication_group_members;"
```

Or using MySQL Shell:

```bash
mysqlsh root:kamo@127.0.0.1:33061 --js -e "dba.getCluster('kamo').status()"
```

## Configuration

### MySQL Configuration Files

- `config/primary.cnf` - Primary node configuration
- `config/secondary1.cnf` - Secondary node 1 configuration
- `config/secondary2.cnf` - Secondary node 2 configuration
- `config/router.conf` - MySQL Router configuration

### Key Configuration Parameters

- **MySQL Version**: 8.0.43 (required for LineairDB support)
- **Group Replication**: Enabled
- **GTID**: Enabled
- **Binary Logging**: ROW format
- **Default Storage Engine**: InnoDB (can be switched to LineairDB)

## Docker Compose Files

### Standard MySQL Cluster

```bash
docker-compose up -d
```

Uses official `mysql:8.0.43` image.

### MySQL Cluster with LineairDB

```bash
docker-compose -f docker-compose-lineairdb.yml up -d
```

Uses custom `mysql-lineairdb:8.0.43` image with LineairDB storage engine support.

## LineairDB Support

### LineairDB Plugin Location

The pre-built LineairDB storage engine plugin is included in this repository:

```
plugins/ha_lineairdb_storage_engine.so
```

This plugin was built from the [LineairDB storage engine](https://github.com/Tatzhiro/LineairDB-storage-engine) project and is compatible with MySQL 8.0.43.

### Building the LineairDB Docker Image

Before using the LineairDB compose file, you need to build the custom Docker image:

```bash
./build-lineairdb-image.sh
```

**Note**: The build script uses the plugin from the build directory at `/work/LineairDB-storage-engine/build`. The pre-built plugin in `plugins/` is provided for convenience.

The build script will:
- Copy MySQL binaries from the build directory
- Copy LineairDB plugin (`ha_lineairdb_storage_engine.so`)
- Copy required libraries (protobuf, etc.)
- Build a Docker image `mysql-lineairdb:8.0.43`

### Install LineairDB Plugin on All Nodes

```bash
./scripts/install-lineairdb-plugin.sh
```

This script will:
- Install the LineairDB storage engine plugin on all cluster nodes (primary and secondaries)
- Verify the plugin is active on each node
- Display the status of LineairDB engine availability

### Switch Storage Engine

```bash
./scripts/switch-to-lineairdb.sh
```

This script will:
- Check if LineairDB plugin is available
- Set default storage engine to LineairDB
- Generate ALTER TABLE statements for existing tables

### Manual Conversion

For existing tables, convert them manually:

```bash
mysql -h 127.0.0.1 -P 6446 --protocol=TCP -u root -pkamo testdb -e "ALTER TABLE your_table ENGINE=LineairDB;"
```

### Create New Tables with LineairDB

```sql
CREATE TABLE test_table (
    id INT PRIMARY KEY AUTO_INCREMENT,
    data VARCHAR(255)
) ENGINE=LineairDB;
```

## Testing the Cluster

### Run Cluster Tests

Test scripts are located in the `tests/` directory:

1. **Comprehensive Test Script** (Recommended):
   ```bash
   ./tests/test-cluster.sh
   ```
   This script runs all tests with detailed output, color coding, and verification:
   - Database and table creation
   - Data insertion
   - Data confirmation
   - Replication verification (read-only port)
   - Transaction testing
   - Node-to-node replication check
   - Direct node access verification

2. **Simple Test Script**:
   ```bash
   ./tests/test-cluster-simple.sh
   ```
   Simpler version without colors, executes all SQL tests.

3. **SQL File** (Execute directly):
   ```bash
   mysql -h 127.0.0.1 -P 6446 --protocol=TCP -u root -pkamo < tests/test-sql.sql
   ```

### Performance Testing

```bash
./scripts/performance-test.sh [host] [port] [iterations] [threads]
```

Example:
```bash
# Test against router (read-write)
./scripts/performance-test.sh localhost 6446 10000 10

# Test against primary directly
./scripts/performance-test.sh localhost 33061 10000 10
```

## Connection Information

### Default Credentials

| Setting | Value |
|---------|-------|
| Root Password | `kamo` |
| Cluster Name | `kamo` |
| Database | `testdb` |
| User | `clusteruser` |
| Password | `kamo` |

**⚠️ WARNING**: Change these passwords in production!

### Connection Strings

**Via Router (Read-Write)**:
```bash
mysql -h 127.0.0.1 -P 6446 --protocol=TCP -u root -pkamo
```

**Via Router (Read-Only)**:
```bash
mysql -h 127.0.0.1 -P 6447 --protocol=TCP -u root -pkamo
```

**Direct to Primary**:
```bash
mysql -h 127.0.0.1 -P 33061 --protocol=TCP -u root -pkamo
```

## Management Commands

### Start Cluster

```bash
docker-compose up -d
# or for LineairDB version:
docker-compose -f docker-compose-lineairdb.yml up -d
```

### Stop Cluster

```bash
docker-compose down
```

### View Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f mysql-primary
docker-compose logs -f mysql-router
```

### Restart Service

```bash
docker-compose restart mysql-primary
```

### Check Container Status

```bash
docker-compose ps
```

### Execute Commands in Container

```bash
docker exec -it mysql-primary bash
docker exec -it mysql-primary mysql -uroot -pkamo
```

## Cleanup Scripts

The `cleanup/` directory contains scripts to clean up the cluster:

### Complete Cleanup (All Containers, Data, and Networks)

```bash
./cleanup/cleanup-all.sh
```

This will:
- Stop and remove all containers
- Remove all data directories
- Remove Docker networks
- Clean up `/etc/hosts` entries

### Containers Only (Preserve Data)

```bash
./cleanup/cleanup-containers-only.sh
```

This will:
- Stop and remove containers
- Remove Docker networks
- **Keep data directories intact**

### Data Only (Keep Containers Running)

```bash
./cleanup/cleanup-data-only.sh
```

This will:
- Stop containers
- Remove all database data
- **Keep containers and networks**

## Monitoring

### Check Group Replication Status

```bash
docker exec -it mysql-primary mysql -uroot -pkamo -e "
SELECT 
    MEMBER_ID,
    MEMBER_HOST,
    MEMBER_PORT,
    MEMBER_STATE,
    MEMBER_ROLE
FROM performance_schema.replication_group_members;
"
```

### Check Replication Lag

```bash
docker exec -it mysql-primary mysql -uroot -pkamo -e "
SHOW SLAVE STATUS\G
"
```

### Check Storage Engines

```bash
docker exec -it mysql-primary mysql -uroot -pkamo -e "SHOW ENGINES;"
```

## Troubleshooting

### Containers Not Starting

1. Check Docker daemon: `docker ps`
2. Check logs: `docker-compose logs`
3. Check disk space: `df -h`
4. Check ports: `netstat -tuln | grep -E '3306|6446|6447'`

### Group Replication Issues

1. Check if all nodes are running: `docker-compose ps`
2. Verify network connectivity between containers
3. Check MySQL error logs: `docker-compose logs mysql-primary`
4. Verify configuration files are correct

### LineairDB Plugin Not Found

1. Verify MySQL version is 8.0.43: `SELECT VERSION();`
2. Check if plugin file exists: `ls docker-build-context/plugins/`
3. Rebuild the LineairDB image: `./build-lineairdb-image.sh`
4. Check plugin installation: `SHOW PLUGINS;`

### Performance Issues

1. Check buffer pool size in configuration
2. Monitor system resources: `htop` or `docker stats`
3. Check replication lag
4. Verify storage engine is correctly set

## File Structure

```
mysql-cluster/
├── docker-compose.yml              # Standard MySQL cluster config
├── docker-compose-lineairdb.yml    # LineairDB-enabled cluster config
├── Dockerfile.mysql-lineairdb      # Dockerfile for LineairDB MySQL image
├── docker-entrypoint.sh            # Custom entrypoint for LineairDB image
├── build-lineairdb-image.sh        # Script to build LineairDB Docker image
├── setup.sh                        # Main setup script
├── check-cluster-status.sh         # Cluster status checker
├── check-environment.sh            # Environment verification script
├── README.md                       # This file
├── SETUP_SUMMARY.md                # Setup summary document
├── plugins/                        # Pre-built LineairDB plugin
│   └── ha_lineairdb_storage_engine.so  # LineairDB storage engine plugin
├── config/                         # Configuration files
│   ├── primary.cnf                 # Primary node config
│   ├── secondary1.cnf              # Secondary node 1 config
│   ├── secondary2.cnf              # Secondary node 2 config
│   └── router.conf                 # Router config
├── scripts/                        # Utility scripts
│   ├── setup-cluster-mysqlshell-8.0.43.sh  # Cluster setup using MySQL Shell
│   ├── install-lineairdb-plugin.sh # Install LineairDB plugin on all nodes
│   ├── switch-to-lineairdb.sh      # Storage engine switch
│   └── performance-test.sh         # Performance testing
├── cleanup/                        # Cleanup scripts
│   ├── cleanup-all.sh              # Complete cleanup
│   ├── cleanup-containers-only.sh  # Cleanup containers only
│   └── cleanup-data-only.sh        # Cleanup data only
├── tests/                          # Test scripts
│   ├── README.md                   # Test documentation
│   ├── test-cluster.sh             # Comprehensive test script
│   ├── test-cluster-simple.sh      # Simple test script
│   └── test-sql.sql                # SQL test file
├── docker-build-context/           # Build context for LineairDB image
│   ├── Dockerfile                  # Copied from Dockerfile.mysql-lineairdb
│   ├── docker-entrypoint.sh        # Entrypoint script
│   ├── bin/                        # MySQL binaries
│   ├── lib/                        # Library dependencies
│   ├── plugins/                    # MySQL plugins (including LineairDB)
│   └── share/                      # MySQL share files
├── data/                           # Data directories (created by Docker)
│   ├── primary/
│   ├── secondary1/
│   └── secondary2/
└── logs/                           # Log files
```

## Notes

1. **MySQL 8.0.43**: This specific version is required for LineairDB support.

2. **MySQL Router Version**: The cluster uses the `latest` MySQL Router tag from [Docker Hub](https://hub.docker.com/r/mysql/mysql-router/tags) (currently 8.0.32), which is compatible with MySQL Server 8.0.43.

3. **LineairDB Plugin**: The pre-built LineairDB storage engine plugin is included at `plugins/ha_lineairdb_storage_engine.so`. You can also rebuild it from the [LineairDB storage engine](https://github.com/Tatzhiro/LineairDB-storage-engine) source.

4. **Data Persistence**: Data is stored in `./data/` directories. To reset the cluster, use `./cleanup/cleanup-all.sh`.

5. **Network**: Containers communicate via a Docker bridge network (172.20.0.0/16).

6. **Security**: Default password is `kamo` for convenience. **Change it in production!**

7. **Cluster Name**: The InnoDB Cluster is named `kamo`.

8. **MySQL Shell Required**: The cluster setup requires MySQL Shell to be installed on the host machine.

## Version History

- **v1.1.0**: Upgraded MySQL from 8.0.32 to 8.0.43 for compatibility with LineairDB storage engine
- **v1.0.1**: Added pre-built LineairDB plugin to repository (`plugins/ha_lineairdb_storage_engine.so`)
- **v1.0.0**: Initial setup with MySQL 8.0.32, 4-node cluster, InnoDB to LineairDB switching capability

## License

This setup is provided as-is for testing and development purposes.

## Support

For issues related to:
- **MySQL Cluster**: Check [MySQL Documentation](https://dev.mysql.com/doc/)
- **LineairDB**: Refer to LineairDB documentation
- **Docker**: Check [Docker Documentation](https://docs.docker.com/)
