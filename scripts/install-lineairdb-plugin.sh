#!/bin/bash
# Install LineairDB storage engine plugin on all cluster nodes
# This script installs the LineairDB plugin on primary and all secondary nodes

set -e

ROOT_PASSWORD="kamo"

# Node connection details (using localhost with mapped ports)
PRIMARY_PORT=33061
SEC1_PORT=33062
SEC2_PORT=33063

echo "=========================================="
echo "Installing LineairDB Storage Engine Plugin"
echo "=========================================="
echo ""

install_plugin() {
    local NODE_NAME=$1
    local PORT=$2
    
    echo "Installing LineairDB plugin on $NODE_NAME (port $PORT)..."
    
    # Check if plugin already installed
    INSTALLED=$(mysql -h 127.0.0.1 -P $PORT --protocol=TCP -u root -p${ROOT_PASSWORD} -N -e "SELECT COUNT(*) FROM INFORMATION_SCHEMA.PLUGINS WHERE PLUGIN_NAME = 'LINEAIRDB';" 2>/dev/null)
    
    if [ "$INSTALLED" == "1" ]; then
        echo "  ✓ LineairDB plugin already installed on $NODE_NAME"
    else
        mysql -h 127.0.0.1 -P $PORT --protocol=TCP -u root -p${ROOT_PASSWORD} -e "INSTALL PLUGIN lineairdb SONAME 'ha_lineairdb_storage_engine.so';" 2>/dev/null
        if [ $? -eq 0 ]; then
            echo "  ✓ LineairDB plugin installed successfully on $NODE_NAME"
        else
            echo "  ✗ Failed to install LineairDB plugin on $NODE_NAME"
            return 1
        fi
    fi
    
    # Verify the plugin is active
    STATUS=$(mysql -h 127.0.0.1 -P $PORT --protocol=TCP -u root -p${ROOT_PASSWORD} -N -e "SELECT PLUGIN_STATUS FROM INFORMATION_SCHEMA.PLUGINS WHERE PLUGIN_NAME = 'LINEAIRDB';" 2>/dev/null)
    echo "  Plugin status: $STATUS"
}

echo "Step 1: Installing on Primary Node"
echo "-----------------------------------"
install_plugin "mysql-primary" $PRIMARY_PORT

echo ""
echo "Step 2: Installing on Secondary Node 1"
echo "---------------------------------------"
install_plugin "mysql-secondary-1" $SEC1_PORT

echo ""
echo "Step 3: Installing on Secondary Node 2"
echo "---------------------------------------"
install_plugin "mysql-secondary-2" $SEC2_PORT

echo ""
echo "=========================================="
echo "Installation Complete!"
echo "=========================================="
echo ""
echo "Verifying LineairDB availability on all nodes:"
echo ""

for PORT in $PRIMARY_PORT $SEC1_PORT $SEC2_PORT; do
    echo "Port $PORT:"
    mysql -h 127.0.0.1 -P $PORT --protocol=TCP -u root -p${ROOT_PASSWORD} -e "SHOW ENGINES;" 2>/dev/null | grep -i lineair || echo "  LineairDB not found!"
done

echo ""
echo "You can now create tables with ENGINE=LINEAIRDB:"
echo "  CREATE TABLE test (id INT PRIMARY KEY, data VARCHAR(255)) ENGINE=LINEAIRDB;"
echo ""

