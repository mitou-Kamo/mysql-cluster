#!/bin/bash
# Docker Entrypoint Script for Ubuntu MySQL Container
# Initializes MySQL and handles environment variables

set -eo pipefail

# Logging functions
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"
}

error() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: $*" >&2
}

# Check if mysqld is the command
if [ "$1" = 'mysqld' ]; then
    # Fix permissions
    chown -R mysql:mysql /var/lib/mysql /var/run/mysqld /var/log/mysql 2>/dev/null || true
    chmod 755 /var/run/mysqld

    # Check if MySQL is already initialized
    if [ ! -d "/var/lib/mysql/mysql" ]; then
        log "Initializing MySQL data directory..."
        
        # Check for required password
        if [ -z "$MYSQL_ROOT_PASSWORD" ] && [ "$MYSQL_ALLOW_EMPTY_PASSWORD" != "yes" ]; then
            error "Database is uninitialized and password options are not specified."
            error "You need to specify one of MYSQL_ROOT_PASSWORD or MYSQL_ALLOW_EMPTY_PASSWORD"
            exit 1
        fi

        # Initialize MySQL
        log "Running mysqld --initialize-insecure..."
        mysqld --initialize-insecure --user=mysql --datadir=/var/lib/mysql
        
        log "Starting MySQL temporarily for setup..."
        mysqld --user=mysql --skip-networking --socket=/var/run/mysqld/mysqld.sock &
        pid="$!"
        
        # Wait for MySQL to be ready
        log "Waiting for MySQL to be ready..."
        for i in {30..0}; do
            if mysqladmin ping --socket=/var/run/mysqld/mysqld.sock --silent; then
                break
            fi
            sleep 1
        done
        
        if [ "$i" = 0 ]; then
            error "MySQL failed to start for initialization"
            exit 1
        fi
        
        log "MySQL is ready for setup"
        
        # Create init SQL file
        init_file="/tmp/mysql-init.sql"
        
        # Set root password
        if [ -n "$MYSQL_ROOT_PASSWORD" ]; then
            log "Setting root password..."
            cat > "$init_file" <<-EOSQL
ALTER USER 'root'@'localhost' IDENTIFIED BY '${MYSQL_ROOT_PASSWORD}';
CREATE USER IF NOT EXISTS 'root'@'%' IDENTIFIED BY '${MYSQL_ROOT_PASSWORD}';
GRANT ALL PRIVILEGES ON *.* TO 'root'@'%' WITH GRANT OPTION;
EOSQL
        else
            cat > "$init_file" <<-EOSQL
CREATE USER IF NOT EXISTS 'root'@'%';
GRANT ALL PRIVILEGES ON *.* TO 'root'@'%' WITH GRANT OPTION;
EOSQL
        fi
        
        # Create database if specified
        if [ -n "$MYSQL_DATABASE" ]; then
            log "Creating database: $MYSQL_DATABASE"
            echo "CREATE DATABASE IF NOT EXISTS \`$MYSQL_DATABASE\`;" >> "$init_file"
        fi
        
        # Create user if specified
        if [ -n "$MYSQL_USER" ] && [ -n "$MYSQL_PASSWORD" ]; then
            log "Creating user: $MYSQL_USER"
            cat >> "$init_file" <<-EOSQL
CREATE USER IF NOT EXISTS '${MYSQL_USER}'@'%' IDENTIFIED BY '${MYSQL_PASSWORD}';
EOSQL
            
            if [ -n "$MYSQL_DATABASE" ]; then
                echo "GRANT ALL ON \`${MYSQL_DATABASE}\`.* TO '${MYSQL_USER}'@'%';" >> "$init_file"
            fi
        fi
        
        # Flush privileges
        echo "FLUSH PRIVILEGES;" >> "$init_file"
        
        # Execute init SQL
        mysql --socket=/var/run/mysqld/mysqld.sock < "$init_file"
        rm -f "$init_file"
        
        # Execute any SQL files in /docker-entrypoint-initdb.d/
        if [ -d "/docker-entrypoint-initdb.d" ]; then
            for f in /docker-entrypoint-initdb.d/*; do
                case "$f" in
                    *.sql)
                        log "Running $f"
                        mysql --socket=/var/run/mysqld/mysqld.sock < "$f"
                        ;;
                    *.sql.gz)
                        log "Running $f"
                        gunzip -c "$f" | mysql --socket=/var/run/mysqld/mysqld.sock
                        ;;
                    *.sh)
                        log "Running $f"
                        . "$f"
                        ;;
                    *)
                        log "Ignoring $f"
                        ;;
                esac
            done
        fi
        
        # Shutdown temporary MySQL
        log "Shutting down temporary MySQL..."
        if ! mysqladmin shutdown --socket=/var/run/mysqld/mysqld.sock; then
            kill "$pid"
        fi
        wait "$pid" || true
        
        log "MySQL initialization completed"
    else
        log "MySQL data directory already exists, skipping initialization"
    fi
    
    # Adjust server-id from environment if provided
    if [ -n "$MYSQL_SERVER_ID" ]; then
        log "Setting server-id to $MYSQL_SERVER_ID"
        echo "[mysqld]" > /etc/mysql/conf.d/server-id.cnf
        echo "server-id=$MYSQL_SERVER_ID" >> /etc/mysql/conf.d/server-id.cnf
    fi
    
    log "Starting MySQL server..."
fi

# Execute the command
exec "$@"

