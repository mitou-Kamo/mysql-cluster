# MySQL Cluster Test Suite

This directory contains test scripts for the MySQL Cluster setup.

## Test Files

1. **`test-cluster.sh`** - Comprehensive test script with detailed output
2. **`test-cluster-simple.sh`** - Simpler version without colors
3. **`test-sql.sql`** - Raw SQL file for manual execution

## Running Tests

### Comprehensive Test (Recommended)
```bash
./test-cluster.sh
```

### Simple Test
```bash
./test-cluster-simple.sh
```

### Execute SQL File Directly
```bash
mysql -h 127.0.0.1 -P 6446 --protocol=TCP -u root -prootpassword < test-sql.sql
```

## Test Coverage

The test suite covers:

1. ✅ **Database and Table Creation** - Creates `kamo_test` database and `mitou_members` table
2. ✅ **Data Insertion** - Inserts 3 initial records (Yusuke, Tatsuhiro, Tony)
3. ✅ **Data Confirmation** - Verifies all records are present
4. ✅ **Replication Confirmation** - Tests read-only port to verify replication
5. ✅ **Transaction Confirmation** - Tests transaction with Rika Shou insertion
6. ⚠️ **Node-to-Node Replication** - Checks server IDs and record counts (requires secondary nodes to be joined)
7. ⚠️ **Direct Node Access** - Verifies all nodes directly (requires secondary nodes to be joined)

## Test Results

### Expected Results (Primary Node Working)
- Tests 1-5 should all pass ✅
- Tests 6-7 may show issues if secondary nodes haven't joined Group Replication

### Current Status
- Primary node: ✅ Working
- Router: ✅ Working
- Secondary nodes: ⚠️ Running but may need Group Replication configuration

## Notes

- The test script automatically cleans up previous test data before running
- Tests use the router ports (6446 for read-write, 6447 for read-only)
- All tests connect via TCP protocol to avoid socket issues

## Troubleshooting

If tests fail:
1. Check cluster status: `../check-cluster-status.sh`
2. Verify router is running: `sudo docker-compose ps mysql-router`
3. Check MySQL logs: `sudo docker-compose logs mysql-primary`
4. Ensure ports 6446-6449 are accessible

