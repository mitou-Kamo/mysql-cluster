#!/bin/bash
# Environment check script for MySQL Cluster setup

echo "=========================================="
echo "MySQL Cluster Environment Check"
echo "=========================================="
echo ""

# System Information
echo "1. System Information:"
echo "   OS: $(cat /etc/os-release | grep PRETTY_NAME | cut -d'"' -f2)"
echo "   Kernel: $(uname -r)"
echo "   Architecture: $(uname -m)"
echo ""

# Disk Space
echo "2. Disk Space:"
df -h | grep -E '^/dev|Filesystem' | head -5
echo ""

# Memory
echo "3. Memory:"
free -h | head -2
echo ""

# Docker Check
echo "4. Docker Status:"
if command -v docker &> /dev/null; then
    echo "   ✓ Docker installed: $(docker --version)"
    if docker ps &> /dev/null; then
        echo "   ✓ Docker daemon is running"
    else
        echo "   ✗ Docker daemon is NOT running"
    fi
else
    echo "   ✗ Docker is NOT installed"
fi
echo ""

# Docker Compose Check
echo "5. Docker Compose Status:"
if command -v docker-compose &> /dev/null; then
    echo "   ✓ Docker Compose installed: $(docker-compose --version)"
else
    echo "   ✗ Docker Compose is NOT installed"
fi
echo ""

# Port Availability
echo "6. Port Availability:"
PORTS=(33061 33062 33063 6446 6447 6448 6449)
for port in "${PORTS[@]}"; do
    if netstat -tuln 2>/dev/null | grep -q ":$port " || ss -tuln 2>/dev/null | grep -q ":$port "; then
        echo "   ✗ Port $port is already in use"
    else
        echo "   ✓ Port $port is available"
    fi
done
echo ""

# Directory Check
echo "7. Directory Structure:"
REQUIRED_DIRS=("config" "scripts" "data/primary" "data/secondary1" "data/secondary2")
for dir in "${REQUIRED_DIRS[@]}"; do
    if [ -d "$dir" ]; then
        echo "   ✓ $dir exists"
    else
        echo "   ✗ $dir is missing"
    fi
done
echo ""

# Configuration Files
echo "8. Configuration Files:"
CONFIG_FILES=("config/primary.cnf" "config/secondary1.cnf" "config/secondary2.cnf" "config/router.conf")
for file in "${CONFIG_FILES[@]}"; do
    if [ -f "$file" ]; then
        echo "   ✓ $file exists"
    else
        echo "   ✗ $file is missing"
    fi
done
echo ""

# Scripts
echo "9. Scripts:"
SCRIPT_FILES=("setup.sh" "scripts/01-init-cluster.sh" "scripts/02-join-secondary.sh" "scripts/switch-to-lineairdb.sh" "scripts/performance-test.sh")
for script in "${SCRIPT_FILES[@]}"; do
    if [ -f "$script" ]; then
        if [ -x "$script" ]; then
            echo "   ✓ $script exists and is executable"
        else
            echo "   ⚠ $script exists but is not executable"
        fi
    else
        echo "   ✗ $script is missing"
    fi
done
echo ""

# Docker Images
echo "10. Docker Images:"
if docker images | grep -q "mysql.*8.0.32"; then
    echo "   ✓ MySQL 8.0.32 image is available"
else
    echo "   ⚠ MySQL 8.0.32 image not found (will be pulled during setup)"
fi

if docker images | grep -q "mysql-router.*8.0.32"; then
    echo "   ✓ MySQL Router 8.0.32 image is available"
else
    echo "   ⚠ MySQL Router 8.0.32 image not found (will be pulled during setup)"
fi
echo ""

# Summary
echo "=========================================="
echo "Environment Check Complete"
echo "=========================================="
echo ""
echo "If all checks pass, you can proceed with:"
echo "  ./setup.sh"
echo ""

