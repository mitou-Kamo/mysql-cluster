#!/bin/bash
# Switch storage engine from InnoDB to LineairDB

set -e

PRIMARY_HOST="mysql-primary"
ROOT_PASSWORD="kamo"
DB_NAME="testdb"

echo "Switching storage engine from InnoDB to LineairDB..."

# Check if LineairDB plugin is available
mysql -h ${PRIMARY_HOST} -u root -p${ROOT_PASSWORD} <<EOF
-- Check if LineairDB plugin exists
SELECT PLUGIN_NAME, PLUGIN_STATUS 
FROM INFORMATION_SCHEMA.PLUGINS 
WHERE PLUGIN_NAME LIKE '%lineair%';

-- Install LineairDB plugin if available
-- INSTALL PLUGIN lineairdb SONAME 'ha_lineairdb.so';

-- Set default storage engine to LineairDB
SET GLOBAL default_storage_engine = 'LineairDB';

-- For existing tables, convert them
USE ${DB_NAME};

-- Get list of tables
SELECT CONCAT('ALTER TABLE ', table_name, ' ENGINE=LineairDB;') 
FROM information_schema.tables 
WHERE table_schema = '${DB_NAME}' 
AND engine = 'InnoDB';
EOF

echo "Storage engine switched to LineairDB"
echo "Note: You may need to manually convert existing tables using ALTER TABLE statements"

