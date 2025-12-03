#!/bin/bash
# Simple test script - executes SQL directly without fancy output

set -e

ROUTER_HOST="127.0.0.1"
ROUTER_RW_PORT="6446"
ROUTER_RO_PORT="6447"
ROOT_USER="root"
ROOT_PASSWORD="kamo"
DB_NAME="kamo_test"

echo "=========================================="
echo "MySQL Cluster Simple Test"
echo "=========================================="
echo ""

# Create database and table
echo "1. Creating database and table..."
mysql -h ${ROUTER_HOST} -P ${ROUTER_RW_PORT} --protocol=TCP -u ${ROOT_USER} -p${ROOT_PASSWORD} <<EOF
CREATE DATABASE IF NOT EXISTS ${DB_NAME};
USE ${DB_NAME};

CREATE TABLE IF NOT EXISTS mitou_members (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(50) NOT NULL,
    age INT NOT NULL,
    role VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
EOF
echo "✓ Database and table created"
echo ""

# Insert data
echo "2. Inserting data..."
mysql -h ${ROUTER_HOST} -P ${ROUTER_RW_PORT} --protocol=TCP -u ${ROOT_USER} -p${ROOT_PASSWORD} ${DB_NAME} <<EOF
INSERT INTO mitou_members (name, age, role) VALUES
('Yusuke Miyazaki', 23, 'B4'),
('Tatsuhiro Nakamori', 25, 'D1'),
('Tony Li', 24, 'M2');
EOF
echo "✓ Data inserted"
echo ""

# Verify data
echo "3. Verifying data..."
mysql -h ${ROUTER_HOST} -P ${ROUTER_RW_PORT} --protocol=TCP -u ${ROOT_USER} -p${ROOT_PASSWORD} ${DB_NAME} -e "SELECT * FROM mitou_members;"
echo ""

# Test replication via read-only port
echo "4. Testing replication (read-only port)..."
mysql -h ${ROUTER_HOST} -P ${ROUTER_RO_PORT} --protocol=TCP -u ${ROOT_USER} -p${ROOT_PASSWORD} ${DB_NAME} -e "SELECT COUNT(*) AS total_records FROM mitou_members;"
echo ""

# Transaction test
echo "5. Testing transaction..."
mysql -h ${ROUTER_HOST} -P ${ROUTER_RW_PORT} --protocol=TCP -u ${ROOT_USER} -p${ROOT_PASSWORD} ${DB_NAME} <<EOF
START TRANSACTION;
INSERT INTO mitou_members (name, age, role) VALUES ('Rika Shou', 22, 'B3');
COMMIT;
EOF
echo "✓ Transaction completed"
echo ""

# Final verification
echo "6. Final verification - All records:"
mysql -h ${ROUTER_HOST} -P ${ROUTER_RW_PORT} --protocol=TCP -u ${ROOT_USER} -p${ROOT_PASSWORD} ${DB_NAME} -e "SELECT * FROM mitou_members;"
echo ""

# Check server IDs
echo "7. Checking server IDs across nodes..."
echo "Read-Write Port:"
mysql -h ${ROUTER_HOST} -P ${ROUTER_RW_PORT} --protocol=TCP -u ${ROOT_USER} -p${ROOT_PASSWORD} -N -e "SELECT @@server_id AS node_id, (SELECT COUNT(*) FROM ${DB_NAME}.mitou_members) AS record_count;"
echo "Read-Only Port:"
mysql -h ${ROUTER_HOST} -P ${ROUTER_RO_PORT} --protocol=TCP -u ${ROOT_USER} -p${ROOT_PASSWORD} -N -e "SELECT @@server_id AS node_id, (SELECT COUNT(*) FROM ${DB_NAME}.mitou_members) AS record_count;"
echo ""

echo "=========================================="
echo "Test completed!"
echo "=========================================="

