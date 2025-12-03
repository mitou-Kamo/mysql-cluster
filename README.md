# MySQL Cluster with LineairDB Storage Engine

This repository contains a complete setup for a MySQL 8.0.32 cluster with 4 nodes (1 primary, 2 secondary, 1 router) using Docker containers. The cluster is configured to support switching from InnoDB to LineairDB storage engine for performance testing.

## System Requirements

- **OS**: Linux (Ubuntu 20.04+ recommended)
- **Docker**: Version 20.10+
- **Docker Compose**: Version 1.25+
- **Disk Space**: Minimum 10GB free space
- **Memory**: Minimum 4GB RAM (8GB+ recommended)

### Docker Permissions

If you encounter permission errors with Docker, you may need to:
1. Add your user to the docker group: `sudo usermod -aG docker $USER`
2. Log out and log back in, or run: `newgrp docker`
3. Alternatively, use `sudo` with docker commands (not recommended for production)

## System Environment

### Current System Status
- **OS**: Ubuntu 20.04.6 LTS (Focal Fossa)
- **Kernel**: Linux 5.4.0-216-generic
- **Architecture**: x86_64
- **Docker**: 28.1.1
- **Docker Compose**: 1.25.0

### Disk Space
- Root filesystem: 8.1GB available (97% used)
- Work filesystem: 9.2TB available (65% used)
- **Recommendation**: Use `/work` directory for data storage if needed

### Memory
- Total: 1.5TB
- Available: 1.3TB

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

### 1. Clone/Download Repository

```bash
cd /home/tonyli_15/mysql-server
```

### 2. Check Environment

```bash
./check-environment.sh
```

This will verify:
- System information
- Disk space and memory
- Docker and Docker Compose installation
- Port availability
- Required directories and files

### 3. Run Setup Script

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

### 4. Cleanup Scripts

The `cleanup/` directory contains scripts to clean up the cluster:

#### Complete Cleanup (All Containers, Data, and Networks)
```bash
./cleanup/cleanup-all.sh
```
This will:
- Stop and remove all containers
- Remove all data directories
- Remove Docker networks
- Clean up `/etc/hosts` entries

#### Containers Only (Preserve Data)
```bash
./cleanup/cleanup-containers-only.sh
```
This will:
- Stop and remove containers
- Remove Docker networks
- **Keep data directories intact**

#### Data Only (Keep Containers Running)
```bash
./cleanup/cleanup-data-only.sh
```
This will:
- Stop containers
- Remove all database data
- **Keep containers and networks**

## Configuration

### MySQL Configuration Files

- `config/primary.cnf` - Primary node configuration
- `config/secondary1.cnf` - Secondary node 1 configuration
- `config/secondary2.cnf` - Secondary node 2 configuration
- `config/router.conf` - MySQL Router configuration

### Key Configuration Parameters

- **MySQL Version**: 8.0.32 (required for LineairDB support)
- **Group Replication**: Enabled
- **GTID**: Enabled
- **Binary Logging**: ROW format
- **Default Storage Engine**: InnoDB (can be switched to LineairDB)

## Switching to LineairDB

### Prerequisites

LineairDB storage engine plugin must be available. The plugin may need to be:
1. Compiled from source
2. Installed as a separate plugin
3. Built into a custom MySQL image

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
mysql -h localhost -P 6446 -u root -prootpassword testdb -e "ALTER TABLE your_table ENGINE=LineairDB;"
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

Three test scripts are available:

1. **Comprehensive Test Script** (Recommended):
   ```bash
   ./test-cluster.sh
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
   ./test-cluster-simple.sh
   ```
   Simpler version without colors, executes all SQL tests.

3. **SQL File** (Execute directly):
   ```bash
   mysql -h localhost -P 6446 -u root -prootpassword < test-sql.sql
   ```
   Or connect and run:
   ```bash
   mysql -h localhost -P 6446 -u root -prootpassword
   source test-sql.sql;
   ```

### Performance Testing

### Run Performance Tests

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

### Manual Performance Testing

Connect to the cluster:

```bash
# Via Router (recommended)
mysql -h localhost -P 6446 -u root -prootpassword

# Direct to Primary
mysql -h localhost -P 33061 -u root -prootpassword

# Direct to Secondary 1
mysql -h localhost -P 33062 -u root -prootpassword
```

## Connection Information

### Default Credentials
- **Root Password**: `kamo`
- **Cluster Name**: `kamo`
- **Database**: `testdb`
- **User**: `clusteruser`
- **Password**: `clusterpass`

**⚠️ WARNING**: Change these passwords in production!

### Connection Strings

**Via Router (Read-Write)**:
```
mysql://root:rootpassword@localhost:6446/testdb
```

**Via Router (Read-Only)**:
```
mysql://root:rootpassword@localhost:6447/testdb
```

**Direct to Primary**:
```
mysql://root:rootpassword@localhost:33061/testdb
```

## Management Commands

### Start Cluster
```bash
docker-compose up -d
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
docker exec -it mysql-primary mysql -uroot -prootpassword
```

## Monitoring

### Check Group Replication Status
```bash
docker exec -it mysql-primary mysql -uroot -prootpassword -e "
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
docker exec -it mysql-primary mysql -uroot -prootpassword -e "
SHOW SLAVE STATUS\G
"
```

### Check Storage Engines
```bash
docker exec -it mysql-primary mysql -uroot -prootpassword -e "SHOW ENGINES;"
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
1. Verify MySQL version is 8.0.32: `SELECT VERSION();`
2. Check if plugin file exists in MySQL plugin directory
3. May need to build custom MySQL image with LineairDB support
4. Check plugin installation: `SHOW PLUGINS;`

### Performance Issues
1. Check buffer pool size in configuration
2. Monitor system resources: `htop` or `docker stats`
3. Check replication lag
4. Verify storage engine is correctly set

## File Structure

```
mysql-server/
├── docker-compose.yml          # Docker Compose configuration
├── setup.sh                     # Main setup script
├── check-cluster-status.sh      # Cluster status checker
├── README.md                    # This file
├── .gitignore                   # Git ignore file
├── config/                      # Configuration files
│   ├── primary.cnf             # Primary node config
│   ├── secondary1.cnf          # Secondary node 1 config
│   ├── secondary2.cnf          # Secondary node 2 config
│   └── router.conf             # Router config
├── scripts/                     # Utility scripts
│   ├── setup-cluster-mysqlshell-8.0.32.sh  # Cluster setup using MySQL Shell (recommended)
│   ├── switch-to-lineairdb.sh  # Storage engine switch
│   └── performance-test.sh     # Performance testing
├── cleanup/                     # Cleanup scripts
│   ├── cleanup-all.sh          # Complete cleanup (containers, data, networks)
│   ├── cleanup-containers-only.sh  # Cleanup containers only (preserve data)
│   └── cleanup-data-only.sh    # Cleanup data only (preserve containers)
├── data/                        # Data directories (created by Docker)
│   ├── primary/
│   ├── secondary1/
│   └── secondary2/
└── logs/                        # Log files (if any)
```

## Notes

1. **MySQL 8.0.32**: This specific version is required for LineairDB support. Other versions may not work.

2. **LineairDB Plugin**: The LineairDB storage engine plugin may need to be:
   - Compiled from source
   - Included in a custom MySQL Docker image
   - Installed separately

3. **Data Persistence**: Data is stored in `./data/` directories. To reset the cluster, use `./cleanup/cleanup-all.sh` or manually delete these directories and restart.

4. **Network**: Containers communicate via a Docker bridge network (172.20.0.0/16).

5. **Security**: Default password is `kamo` for convenience. **Change it in production!**
6. **Cluster Name**: The InnoDB Cluster is named `kamo`. You can check status with: `mysqlsh root:kamo@127.0.0.1:33061 --js -e "dba.getCluster('kamo').status()"`

## Contributing

To replicate this setup:

1. Fork/clone this repository
2. Ensure Docker and Docker Compose are installed
3. Run `./setup.sh`
4. Follow the instructions in this README

## License

This setup is provided as-is for testing and development purposes.

## Support

For issues related to:
- **MySQL Cluster**: Check MySQL documentation
- **LineairDB**: Refer to LineairDB documentation
- **Docker**: Check Docker documentation

## Version History

- **v1.0.0**: Initial setup with MySQL 8.0.32, 4-node cluster, InnoDB to LineairDB switching capability

