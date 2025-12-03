#!/bin/bash
# Check MySQL Cluster status

PRIMARY_HOST="mysql-primary"
ROOT_PASSWORD="kamo"

echo "=========================================="
echo "MySQL Cluster Status"
echo "=========================================="

echo ""
echo "Group Replication Members:"
sudo docker exec ${PRIMARY_HOST} mysql -uroot -p${ROOT_PASSWORD} -e "
SELECT 
    MEMBER_ID,
    MEMBER_HOST,
    MEMBER_PORT,
    MEMBER_STATE,
    MEMBER_ROLE
FROM performance_schema.replication_group_members;
"

echo ""
echo "Group Replication Status:"
sudo docker exec ${PRIMARY_HOST} mysql -uroot -p${ROOT_PASSWORD} -e "
SELECT 
    VARIABLE_NAME,
    VARIABLE_VALUE
FROM performance_schema.global_status
WHERE VARIABLE_NAME LIKE 'group_replication%';
"

echo ""
echo "Storage Engines:"
sudo docker exec ${PRIMARY_HOST} mysql -uroot -p${ROOT_PASSWORD} -e "
SHOW ENGINES;
"

echo ""
echo "Container Status:"
sudo docker-compose ps

