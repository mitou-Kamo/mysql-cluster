#!/bin/bash
# Performance testing script for MySQL Cluster

set -e

HOST=${1:-"localhost"}
PORT=${2:-"6446"}
DB_NAME="testdb"
ROOT_PASSWORD="kamo"
ITERATIONS=${3:-1000}
THREADS=${4:-10}

echo "Starting performance test..."
echo "Host: ${HOST}:${PORT}"
echo "Database: ${DB_NAME}"
echo "Iterations: ${ITERATIONS}"
echo "Threads: ${THREADS}"

# Create test table
mysql -h ${HOST} -P ${PORT} --protocol=TCP -u root -p${ROOT_PASSWORD} <<EOF
USE ${DB_NAME};

-- Create test table
CREATE TABLE IF NOT EXISTS perf_test (
    id INT AUTO_INCREMENT PRIMARY KEY,
    data VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_created (created_at)
) ENGINE=InnoDB;

-- Truncate table
TRUNCATE TABLE perf_test;
EOF

# Insert performance test
echo "Testing INSERT performance..."
time mysql -h ${HOST} -P ${PORT} --protocol=TCP -u root -p${ROOT_PASSWORD} ${DB_NAME} <<EOF
DELIMITER //
CREATE PROCEDURE IF NOT EXISTS insert_test()
BEGIN
    DECLARE i INT DEFAULT 1;
    WHILE i <= ${ITERATIONS} DO
        INSERT INTO perf_test (data) VALUES (CONCAT('test_data_', i));
        SET i = i + 1;
    END WHILE;
END//
DELIMITER ;

CALL insert_test();
EOF

# Select performance test
echo "Testing SELECT performance..."
time mysql -h ${HOST} -P ${PORT} --protocol=TCP -u root -p${ROOT_PASSWORD} ${DB_NAME} -e "
SELECT COUNT(*) as total_records FROM perf_test;
SELECT * FROM perf_test LIMIT 10;
"

# Update performance test
echo "Testing UPDATE performance..."
time mysql -h ${HOST} -P ${PORT} --protocol=TCP -u root -p${ROOT_PASSWORD} ${DB_NAME} <<EOF
UPDATE perf_test SET data = CONCAT(data, '_updated') WHERE id <= 100;
EOF

# Delete performance test
echo "Testing DELETE performance..."
time mysql -h ${HOST} -P ${PORT} --protocol=TCP -u root -p${ROOT_PASSWORD} ${DB_NAME} <<EOF
DELETE FROM perf_test WHERE id > ${ITERATIONS} - 100;
EOF

echo "Performance test completed!"

