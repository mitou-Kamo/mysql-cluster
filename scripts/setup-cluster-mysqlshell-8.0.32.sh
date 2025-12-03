#!/bin/bash
# Setup MySQL InnoDB Cluster using MySQL Shell 8.0.32
# Using dba.configureInstance() and cluster.addInstance() - Recommended Method
# Reference: https://blog.s-style.co.jp/2024/09/2722/#index_id5

set -e

# Connection details - using localhost with mapped ports
PRIMARY_URI="root:kamo@127.0.0.1:33061"
SEC1_URI="root:kamo@127.0.0.1:33062"
SEC2_URI="root:kamo@127.0.0.1:33063"
CLUSTER_NAME="kamo"

# Container hostnames for localAddress (must use MySQL Server port 3306, not 33061)
PRIMARY_LOCAL="mysql-primary:3306"
SEC1_LOCAL="mysql-secondary-1:3306"
SEC2_LOCAL="mysql-secondary-2:3306"

echo "=========================================="
echo "Setting up MySQL InnoDB Cluster"
echo "Using MySQL Shell with dba.configureInstance() and cluster.addInstance()"
echo "=========================================="
echo ""

# Check MySQL Shell version
if ! command -v mysqlsh &> /dev/null; then
    echo "ERROR: MySQL Shell (mysqlsh) is not installed!"
    echo ""
    echo "Please install MySQL Shell 8.0.32:"
    echo "  Download from: https://dev.mysql.com/downloads/shell/"
    echo "  Or use: wget https://dev.mysql.com/get/Downloads/MySQL-Shell/mysql-shell-8.0.32-linux-glibc2.12-x86-64bit.tar.gz"
    exit 1
fi

MYSQLSH_VERSION=$(mysqlsh --version 2>&1 | grep -oP 'Ver \K[0-9]+\.[0-9]+\.[0-9]+' | head -1)
echo "MySQL Shell version: $MYSQLSH_VERSION"
echo "Target MySQL version: 8.0.32"
echo ""

# Step 1: Configure Primary Instance
echo "Step 1: Configuring Primary Instance"
echo "-------------------------------------"
mysqlsh ${PRIMARY_URI} --js --no-wizard <<EOF
print('Configuring primary instance...');
try {
    var result = dba.configureInstance('${PRIMARY_URI}');
    print('Primary instance configured successfully');
} catch(e) {
    if (e.message.includes('already configured') || e.message.includes('already been configured')) {
        print('Primary instance already configured');
    } else {
        print('Error: ' + e.message);
        throw e;
    }
}
EOF

echo ""
echo "Step 2: Creating Cluster"
echo "------------------------"
mysqlsh ${PRIMARY_URI} --js --no-wizard <<EOF
shell.options.useWizards = false;
print('Creating or getting cluster...');
var cluster;
try {
    cluster = dba.getCluster('${CLUSTER_NAME}');
    print('Cluster already exists, using existing cluster: ' + cluster.getName());
} catch(e) {
    if (e.message.includes('not found') || e.message.includes('does not exist') || e.message.includes('standalone instance')) {
        print('Creating new cluster...');
        cluster = dba.createCluster('${CLUSTER_NAME}', {
            localAddress: '${PRIMARY_LOCAL}'
        });
        print('Cluster created: ' + cluster.getName());
    } else {
        throw e;
    }
}
print('\\nInitial cluster status:');
cluster.status();
EOF

echo ""
echo "Step 3: Configuring Secondary Instance 1"
echo "------------------------------------------"
mysqlsh ${SEC1_URI} --js --no-wizard <<EOF
shell.options.useWizards = false;
print('Configuring secondary instance 1...');
try {
    var result = dba.configureInstance('${SEC1_URI}');
    print('Secondary instance 1 configured successfully');
} catch(e) {
    if (e.message.includes('already configured') || e.message.includes('already been configured')) {
        print('Secondary instance 1 already configured');
    } else {
        print('Error: ' + e.message);
        throw e;
    }
}
EOF

echo ""
echo "Step 4: Adding Secondary Instance 1 to Cluster"
echo "------------------------------------------------"
mysqlsh ${PRIMARY_URI} --js --no-wizard <<EOF
var cluster = dba.getCluster('${CLUSTER_NAME}');
print('Adding secondary instance 1 to cluster...');
try {
    cluster.addInstance('${SEC1_URI}', {
        recoveryMethod: 'clone',
        localAddress: '${SEC1_LOCAL}'
    });
    print('Secondary instance 1 added successfully');
    print('\\nCluster status after adding instance 1:');
    cluster.status();
} catch(e) {
    print('Error adding instance: ' + e.message);
    throw e;
}
EOF

echo ""
echo "Step 5: Configuring Secondary Instance 2"
echo "------------------------------------------"
mysqlsh ${SEC2_URI} --js --no-wizard <<EOF
shell.options.useWizards = false;
print('Configuring secondary instance 2...');
try {
    var result = dba.configureInstance('${SEC2_URI}');
    print('Secondary instance 2 configured successfully');
} catch(e) {
    if (e.message.includes('already configured') || e.message.includes('already been configured')) {
        print('Secondary instance 2 already configured');
    } else {
        print('Error: ' + e.message);
        throw e;
    }
}
EOF

echo ""
echo "Step 6: Adding Secondary Instance 2 to Cluster"
echo "------------------------------------------------"
mysqlsh ${PRIMARY_URI} --js --no-wizard <<EOF
var cluster = dba.getCluster('${CLUSTER_NAME}');
print('Adding secondary instance 2 to cluster...');
try {
    cluster.addInstance('${SEC2_URI}', {
        recoveryMethod: 'clone',
        localAddress: '${SEC2_LOCAL}'
    });
    print('Secondary instance 2 added successfully');
} catch(e) {
    print('Error adding instance: ' + e.message);
    throw e;
}
EOF

echo ""
echo "=========================================="
echo "Cluster Setup Complete!"
echo "=========================================="
echo ""
echo "Final Cluster Status:"
mysqlsh ${PRIMARY_URI} --js --no-wizard <<EOF
var cluster = dba.getCluster('${CLUSTER_NAME}');
cluster.status();
EOF

echo ""
echo "You can check cluster status anytime with:"
echo "  mysqlsh ${PRIMARY_URI} --js -e \"dba.getCluster('${CLUSTER_NAME}').status()\""

