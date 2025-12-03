#!/bin/bash
# Cleanup data only - keeps containers running

set -e

echo "=========================================="
echo "MySQL Cluster Data Cleanup"
echo "=========================================="
echo ""

read -p "This will DELETE all database data. Continue? (yes/no): " confirm
if [ "$confirm" != "yes" ]; then
    echo "Cleanup cancelled."
    exit 0
fi

echo ""
echo "Stopping containers..."
cd /home/tonyli_15/mysql-server
sudo docker-compose stop

echo ""
echo "Removing data directories..."
sudo rm -rf data/primary/*
sudo rm -rf data/secondary1/*
sudo rm -rf data/secondary2/*

echo ""
echo "Data cleanup complete!"
echo "Run ./setup.sh to restart with fresh data."

