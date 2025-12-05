#!/bin/bash
# Complete cleanup script for MySQL Cluster
# This will stop and remove all containers, networks, and data

set -e

echo "=========================================="
echo "MySQL Cluster Cleanup Script"
echo "=========================================="
echo ""

# Confirm before proceeding
read -p "This will DELETE all containers, data, and networks. Continue? (yes/no): " confirm
if [ "$confirm" != "yes" ]; then
    echo "Cleanup cancelled."
    exit 0
fi

echo ""
echo "Step 1: Stopping and removing containers..."
cd "$(dirname "$0")/.."
sudo docker-compose down -v

echo ""
echo "Step 2: Removing data directories..."
sudo rm -rf data/primary/*
sudo rm -rf data/secondary1/*
sudo rm -rf data/secondary2/*

echo ""
echo "Step 3: Removing Docker network (if exists)..."
sudo docker network rm mysql-server_mysql-cluster 2>/dev/null || echo "Network already removed or doesn't exist"

echo ""
echo "Step 4: Cleaning up /etc/hosts entries..."
sudo sed -i '/mysql-primary/d' /etc/hosts 2>/dev/null || true
sudo sed -i '/mysql-secondary-1/d' /etc/hosts 2>/dev/null || true
sudo sed -i '/mysql-secondary-2/d' /etc/hosts 2>/dev/null || true

echo ""
echo "Step 5: Verifying cleanup..."
echo "Containers:"
sudo docker ps -a | grep -E "mysql-primary|mysql-secondary|mysql-router" || echo "  No MySQL containers found"

echo ""
echo "Networks:"
sudo docker network ls | grep mysql-cluster || echo "  No MySQL cluster network found"

echo ""
echo "=========================================="
echo "Cleanup Complete!"
echo "=========================================="
echo ""
echo "All containers, data, and networks have been removed."
echo "You can now run ./setup.sh to start fresh."

