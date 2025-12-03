#!/bin/bash
# Quick cleanup - only containers and networks, keep data

set -e

echo "=========================================="
echo "MySQL Cluster Quick Cleanup (Containers Only)"
echo "=========================================="
echo ""

echo "Stopping and removing containers..."
cd /home/tonyli_15/mysql-server
sudo docker-compose down

echo ""
echo "Removing Docker network..."
sudo docker network rm mysql-server_mysql-cluster 2>/dev/null || echo "Network already removed or doesn't exist"

echo ""
echo "Cleanup complete! Data directories are preserved."
echo "Run ./setup.sh to restart containers."

