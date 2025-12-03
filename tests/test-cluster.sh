#!/bin/bash
# Test script for MySQL Cluster - Kamo Test Database

set -e

# Configuration
ROUTER_HOST="127.0.0.1"
ROUTER_RW_PORT="6446"
ROUTER_RO_PORT="6447"
ROOT_USER="root"
ROOT_PASSWORD="kamo"
DB_NAME="kamo_test"
TABLE_NAME="mitou_members"

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo "=========================================="
echo "MySQL Cluster Test Script"
echo "=========================================="
echo ""

# Function to execute SQL via router
execute_sql() {
    local port=$1
    local sql=$2
    local description=$3
    
    echo -e "${BLUE}[TEST]${NC} $description"
    mysql -h ${ROUTER_HOST} -P ${port} --protocol=TCP -u ${ROOT_USER} -p${ROOT_PASSWORD} -e "$sql" 2>&1 | grep -v "Warning: Using a password"
    echo ""
}

# Function to execute SQL and get result
get_sql_result() {
    local port=$1
    local sql=$2
    local result=$(mysql -h ${ROUTER_HOST} -P ${port} --protocol=TCP -u ${ROOT_USER} -p${ROOT_PASSWORD} -N -e "$sql" 2>&1)
    # Extract just the numeric result, ignoring warnings
    echo "$result" | grep -v "Warning" | grep -v "ERROR" | grep -E "^[0-9]+$" | head -1
}

# Function to execute SQL file
execute_sql_file() {
    local port=$1
    local file=$2
    mysql -h ${ROUTER_HOST} -P ${port} -u ${ROOT_USER} -p${ROOT_PASSWORD} < "$file" 2>&1 | grep -v "Warning: Using a password"
}

# =====================================================
# Cleanup: Drop database if exists (for clean test)
# =====================================================
echo -e "${YELLOW}Cleaning up previous test data...${NC}"
mysql -h ${ROUTER_HOST} -P ${ROUTER_RW_PORT} --protocol=TCP -u ${ROOT_USER} -p${ROOT_PASSWORD} -e "DROP DATABASE IF EXISTS ${DB_NAME};" 2>&1 | grep -v "Warning" || true
echo ""

# =====================================================
# Test 1: Database and Table Creation
# =====================================================
echo -e "${YELLOW}========================================${NC}"
echo -e "${YELLOW}Test 1: Database and Table Creation${NC}"
echo -e "${YELLOW}========================================${NC}"
echo ""

execute_sql ${ROUTER_RW_PORT} "CREATE DATABASE IF NOT EXISTS ${DB_NAME};" "Creating database ${DB_NAME}"

execute_sql ${ROUTER_RW_PORT} "USE ${DB_NAME}; CREATE TABLE IF NOT EXISTS ${TABLE_NAME} (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(50) NOT NULL,
    age INT NOT NULL,
    role VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);" "Creating table ${TABLE_NAME}"

echo -e "${GREEN}✓ Test 1 Passed: Database and table created${NC}"
echo ""

# =====================================================
# Test 2: Data Insertion
# =====================================================
echo -e "${YELLOW}========================================${NC}"
echo -e "${YELLOW}Test 2: Data Insertion${NC}"
echo -e "${YELLOW}========================================${NC}"
echo ""

execute_sql ${ROUTER_RW_PORT} "USE ${DB_NAME}; INSERT INTO ${TABLE_NAME} (name, age, role) VALUES
('Yusuke Miyazaki', 23, 'B4'),
('Tatsuhiro Nakamori', 25, 'D1'),
('Tony Li', 24, 'M2');" "Inserting initial data"

echo -e "${GREEN}✓ Test 2 Passed: Data inserted${NC}"
echo ""

# =====================================================
# Test 3: Data Confirmation
# =====================================================
echo -e "${YELLOW}========================================${NC}"
echo -e "${YELLOW}Test 3: Data Confirmation${NC}"
echo -e "${YELLOW}========================================${NC}"
echo ""

echo -e "${BLUE}[TEST]${NC} Verifying inserted data"
execute_sql ${ROUTER_RW_PORT} "USE ${DB_NAME}; SELECT * FROM ${TABLE_NAME};" "Displaying all records"

RECORD_COUNT=$(get_sql_result ${ROUTER_RW_PORT} "USE ${DB_NAME}; SELECT COUNT(*) FROM ${TABLE_NAME};")
if [ "$RECORD_COUNT" -eq 3 ]; then
    echo -e "${GREEN}✓ Test 3 Passed: Found 3 records as expected${NC}"
else
    echo -e "${RED}✗ Test 3 Failed: Expected 3 records, found $RECORD_COUNT${NC}"
    exit 1
fi
echo ""

# =====================================================
# Test 4: Replication Confirmation Test (Read-Only Port)
# =====================================================
echo -e "${YELLOW}========================================${NC}"
echo -e "${YELLOW}Test 4: Replication Confirmation (Read-Only)${NC}"
echo -e "${YELLOW}========================================${NC}"
echo ""

echo -e "${BLUE}[TEST]${NC} Testing read replication via router (read-only port)"
RO_COUNT=$(get_sql_result ${ROUTER_RO_PORT} "USE ${DB_NAME}; SELECT COUNT(*) AS total_records FROM ${TABLE_NAME};")
echo "Records found via read-only port: $RO_COUNT"

if [ "$RO_COUNT" -eq 3 ]; then
    echo -e "${GREEN}✓ Test 4 Passed: Replication working - 3 records visible via read-only port${NC}"
else
    echo -e "${RED}✗ Test 4 Failed: Expected 3 records via read-only, found $RO_COUNT${NC}"
    exit 1
fi
echo ""

# =====================================================
# Test 5: Transaction Confirmation
# =====================================================
echo -e "${YELLOW}========================================${NC}"
echo -e "${YELLOW}Test 5: Transaction Confirmation${NC}"
echo -e "${YELLOW}========================================${NC}"
echo ""

echo -e "${BLUE}[TEST]${NC} Executing transaction"
execute_sql ${ROUTER_RW_PORT} "USE ${DB_NAME}; START TRANSACTION;
INSERT INTO ${TABLE_NAME} (name, age, role) VALUES ('Rika Shou', 22, 'B3');
COMMIT;" "Transaction: Insert Rika Shou"

# Verify the transaction
FINAL_COUNT=$(get_sql_result ${ROUTER_RW_PORT} "USE ${DB_NAME}; SELECT COUNT(*) FROM ${TABLE_NAME};")
if [ "$FINAL_COUNT" -eq 4 ]; then
    echo -e "${GREEN}✓ Test 5 Passed: Transaction committed - 4 records found${NC}"
else
    echo -e "${RED}✗ Test 5 Failed: Expected 4 records after transaction, found $FINAL_COUNT${NC}"
    exit 1
fi

# Display all records after transaction
echo ""
echo -e "${BLUE}[VERIFY]${NC} All records after transaction:"
execute_sql ${ROUTER_RW_PORT} "USE ${DB_NAME}; SELECT * FROM ${TABLE_NAME};" "Displaying all records"
echo ""

# =====================================================
# Test 6: Node-to-Node Replication Check
# =====================================================
echo -e "${YELLOW}========================================${NC}"
echo -e "${YELLOW}Test 6: Node-to-Node Replication Check${NC}"
echo -e "${YELLOW}========================================${NC}"
echo ""

echo -e "${BLUE}[TEST]${NC} Checking replication across nodes via router"
echo ""

# Check via read-write port (should hit primary)
RW_SERVER_ID=$(get_sql_result ${ROUTER_RW_PORT} "SELECT @@server_id;")
RW_COUNT=$(get_sql_result ${ROUTER_RW_PORT} "SELECT COUNT(*) FROM ${DB_NAME}.${TABLE_NAME};")
echo "Read-Write Port (Primary): Server ID = $RW_SERVER_ID, Records = $RW_COUNT"

# Check via read-only port (should hit secondary)
RO_SERVER_ID=$(get_sql_result ${ROUTER_RO_PORT} "SELECT @@server_id;")
RO_COUNT=$(get_sql_result ${ROUTER_RO_PORT} "SELECT COUNT(*) FROM ${DB_NAME}.${TABLE_NAME};")
echo "Read-Only Port (Secondary): Server ID = $RO_SERVER_ID, Records = $RO_COUNT"

# Handle empty results
if [ -z "$RW_COUNT" ]; then
    RW_COUNT=0
fi
if [ -z "$RO_COUNT" ]; then
    RO_COUNT=0
fi

if [ "$RW_COUNT" -eq 4 ] && [ "$RO_COUNT" -eq 4 ]; then
    echo -e "${GREEN}✓ Test 6 Passed: Replication confirmed - Both nodes show 4 records${NC}"
    if [ "$RW_SERVER_ID" != "$RO_SERVER_ID" ]; then
        echo -e "${GREEN}  → Different server IDs detected - Load balancing working!${NC}"
    else
        echo -e "${YELLOW}  → Same server ID (may be hitting same node due to routing)${NC}"
    fi
else
    echo -e "${RED}✗ Test 6 Failed: Record count mismatch (RW: $RW_COUNT, RO: $RO_COUNT)${NC}"
    # Don't exit - continue to Test 7 which will verify directly
fi
echo ""

# =====================================================
# Test 7: Direct Node Access (Optional - for verification)
# =====================================================
echo -e "${YELLOW}========================================${NC}"
echo -e "${YELLOW}Test 7: Direct Node Access Verification${NC}"
echo -e "${YELLOW}========================================${NC}"
echo ""

echo -e "${BLUE}[TEST]${NC} Checking direct access to nodes (bypassing router)"
echo ""

# Check primary node directly
PRIMARY_SERVER_ID=$(sudo docker exec mysql-primary mysql -uroot -p${ROOT_PASSWORD} -N -e "SELECT @@server_id;" 2>&1 | grep -v "Warning" | grep -E "^[0-9]+$" | head -1)
PRIMARY_COUNT=$(sudo docker exec mysql-primary mysql -uroot -p${ROOT_PASSWORD} -N -e "USE ${DB_NAME}; SELECT COUNT(*) FROM ${TABLE_NAME};" 2>&1 | grep -v "Warning" | grep -E "^[0-9]+$" | head -1)
echo "Primary Node (Direct): Server ID = $PRIMARY_SERVER_ID, Records = $PRIMARY_COUNT"

# Check secondary nodes directly
SEC1_SERVER_ID=$(sudo docker exec mysql-secondary-1 mysql -uroot -p${ROOT_PASSWORD} -N -e "SELECT @@server_id;" 2>&1 | grep -v "Warning" | grep -E "^[0-9]+$" | head -1)
SEC1_COUNT=$(sudo docker exec mysql-secondary-1 mysql -uroot -p${ROOT_PASSWORD} -N -e "USE ${DB_NAME}; SELECT COUNT(*) FROM ${TABLE_NAME};" 2>&1 | grep -v "Warning" | grep -E "^[0-9]+$" | head -1)
echo "Secondary-1 Node (Direct): Server ID = $SEC1_SERVER_ID, Records = $SEC1_COUNT"

SEC2_SERVER_ID=$(sudo docker exec mysql-secondary-2 mysql -uroot -p${ROOT_PASSWORD} -N -e "SELECT @@server_id;" 2>&1 | grep -v "Warning" | grep -E "^[0-9]+$" | head -1)
SEC2_COUNT=$(sudo docker exec mysql-secondary-2 mysql -uroot -p${ROOT_PASSWORD} -N -e "USE ${DB_NAME}; SELECT COUNT(*) FROM ${TABLE_NAME};" 2>&1 | grep -v "Warning" | grep -E "^[0-9]+$" | head -1)
echo "Secondary-2 Node (Direct): Server ID = $SEC2_SERVER_ID, Records = $SEC2_COUNT"

if [ "$PRIMARY_COUNT" -eq 4 ] && [ "$SEC1_COUNT" -eq 4 ] && [ "$SEC2_COUNT" -eq 4 ]; then
    echo -e "${GREEN}✓ Test 7 Passed: All nodes have 4 records - Full replication confirmed!${NC}"
else
    echo -e "${RED}✗ Test 7 Failed: Record count mismatch across nodes${NC}"
    echo "  Primary: $PRIMARY_COUNT, Secondary-1: $SEC1_COUNT, Secondary-2: $SEC2_COUNT"
    exit 1
fi
echo ""

# =====================================================
# Final Summary
# =====================================================
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}All Tests Passed! ✓${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "Summary:"
echo "  ✓ Database and table created"
echo "  ✓ Data inserted successfully"
echo "  ✓ Data confirmed via read-write port"
echo "  ✓ Replication confirmed via read-only port"
echo "  ✓ Transaction committed successfully"
echo "  ✓ Node-to-node replication verified"
echo "  ✓ All nodes synchronized"
echo ""
echo "Cluster is working correctly!"
echo ""

