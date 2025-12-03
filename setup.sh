#!/bin/bash
# Main setup script for MySQL Cluster with LineairDB

set -e

echo "=========================================="
echo "MySQL Cluster Setup Script"
echo "=========================================="

# Check prerequisites
echo "Checking prerequisites..."

if ! command -v docker &> /dev/null; then
    echo "Error: Docker is not installed"
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo "Error: Docker Compose is not installed"
    exit 1
fi

echo "✓ Docker and Docker Compose are installed"

# Create necessary directories
echo "Creating directories..."
mkdir -p config
mkdir -p data/primary
mkdir -p data/secondary1
mkdir -p data/secondary2
mkdir -p scripts
mkdir -p logs

# Set permissions
chmod +x scripts/*.sh 2>/dev/null || true

# Pull MySQL 8.0.32 image
echo "Pulling MySQL 8.0.32 image..."
docker pull mysql:8.0.32
docker pull mysql/mysql-router:8.0.32

# Start containers
echo "Starting MySQL cluster containers..."
docker-compose up -d

# Wait for services to be ready
echo "Waiting for services to start..."
sleep 45

# Check if MySQL Shell is available
if ! command -v mysqlsh &> /dev/null; then
    echo ""
    echo "⚠️  WARNING: MySQL Shell is not installed!"
    echo "   Containers are running, but cluster setup requires MySQL Shell."
    echo "   Install MySQL Shell and then run:"
    echo "     ./scripts/setup-cluster-mysqlshell-8.0.32.sh"
    echo ""
    echo "   Or install MySQL Shell:"
    echo "     Ubuntu/Debian: sudo apt-get install mysql-shell"
    echo "     CentOS/RHEL:   sudo yum install mysql-shell"
    echo ""
else
    echo "MySQL Shell found. Setting up cluster..."
    echo ""
    
    # Add Docker hostnames to /etc/hosts if not present
    if ! grep -q "mysql-primary" /etc/hosts 2>/dev/null; then
        echo "Adding Docker hostnames to /etc/hosts (requires sudo)..."
        echo "172.20.0.10 mysql-primary" | sudo tee -a /etc/hosts > /dev/null 2>&1 || echo "  Note: Could not add to /etc/hosts automatically. Please add manually or run cluster setup script separately."
        echo "172.20.0.11 mysql-secondary-1" | sudo tee -a /etc/hosts > /dev/null 2>&1 || true
        echo "172.20.0.12 mysql-secondary-2" | sudo tee -a /etc/hosts > /dev/null 2>&1 || true
    fi
    
    # Run cluster setup
    ./scripts/setup-cluster-mysqlshell-8.0.32.sh
fi

echo "=========================================="
echo "Setup completed!"
echo "=========================================="
echo ""
echo "Cluster Status:"
echo "  Primary:   localhost:33061"
echo "  Secondary 1: localhost:33062"
echo "  Secondary 2: localhost:33063"
echo "  Router:    localhost:6446 (RW), localhost:6447 (RO)"
echo ""
echo "To check cluster status:"
echo "  ./check-cluster-status.sh"
echo "  Or: mysqlsh root:kamo@127.0.0.1:33061 --js -e \"dba.getCluster('kamo').status()\""
echo ""
echo "To switch to LineairDB:"
echo "  ./scripts/switch-to-lineairdb.sh"
echo ""

