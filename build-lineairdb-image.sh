#!/bin/bash
# Build MySQL with LineairDB Docker image
# This script prepares the build context and creates the Docker image

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUILD_DIR="/work/LineairDB-storage-engine/build"
BUILD_CONTEXT="$SCRIPT_DIR/docker-build-context"

echo "=== Building MySQL with LineairDB Docker Image ==="

# Check if build directory exists
if [ ! -d "$BUILD_DIR" ]; then
    echo "ERROR: Build directory not found: $BUILD_DIR"
    echo "Please build LineairDB storage engine first."
    exit 1
fi

# Clean up any existing build context
rm -rf "$BUILD_CONTEXT"
mkdir -p "$BUILD_CONTEXT/bin" "$BUILD_CONTEXT/plugins" "$BUILD_CONTEXT/share"

echo "Copying MySQL binaries..."
# Copy essential MySQL binaries
cp "$BUILD_DIR/runtime_output_directory/mysqld" "$BUILD_CONTEXT/bin/"
cp "$BUILD_DIR/runtime_output_directory/mysql" "$BUILD_CONTEXT/bin/"
cp "$BUILD_DIR/runtime_output_directory/mysqladmin" "$BUILD_CONTEXT/bin/"
cp "$BUILD_DIR/runtime_output_directory/mysqlbinlog" "$BUILD_CONTEXT/bin/"
cp "$BUILD_DIR/runtime_output_directory/mysqldump" "$BUILD_CONTEXT/bin/"
cp "$BUILD_DIR/runtime_output_directory/mysqlcheck" "$BUILD_CONTEXT/bin/"
cp "$BUILD_DIR/runtime_output_directory/mysqlimport" "$BUILD_CONTEXT/bin/"
cp "$BUILD_DIR/runtime_output_directory/mysql_secure_installation" "$BUILD_CONTEXT/bin/"
cp "$BUILD_DIR/runtime_output_directory/mysql_upgrade" "$BUILD_CONTEXT/bin/"
cp "$BUILD_DIR/runtime_output_directory/mysql_tzinfo_to_sql" "$BUILD_CONTEXT/bin/"

echo "Copying plugins (including LineairDB)..."
# Copy all plugins
cp -r "$BUILD_DIR/plugin_output_directory/"* "$BUILD_CONTEXT/plugins/"

echo "Copying library dependencies..."
mkdir -p "$BUILD_CONTEXT/lib"
# Copy protobuf and other required libraries
cp "$BUILD_DIR/library_output_directory/libprotobuf-lite.so.3.19.4" "$BUILD_CONTEXT/lib/"
cp "$BUILD_DIR/library_output_directory/libprotobuf.so.3.19.4" "$BUILD_CONTEXT/lib/"
cp "$BUILD_DIR/library_output_directory/libmysqlclient.so.21.2.32" "$BUILD_CONTEXT/lib/"
# Create symlinks
cd "$BUILD_CONTEXT/lib"
ln -sf libprotobuf-lite.so.3.19.4 libprotobuf-lite.so
ln -sf libprotobuf.so.3.19.4 libprotobuf.so
ln -sf libmysqlclient.so.21.2.32 libmysqlclient.so.21
ln -sf libmysqlclient.so.21 libmysqlclient.so
cd "$SCRIPT_DIR"

# Verify LineairDB plugin is present
if [ ! -f "$BUILD_CONTEXT/plugins/ha_lineairdb_storage_engine.so" ]; then
    echo "WARNING: LineairDB plugin not found in build!"
fi

echo "Copying share directory..."
# Copy share directory (character sets, error messages, etc.)
cp -r "$BUILD_DIR/share/"* "$BUILD_CONTEXT/share/"

echo "Copying Dockerfile and entrypoint..."
cp "$SCRIPT_DIR/Dockerfile.mysql-lineairdb" "$BUILD_CONTEXT/Dockerfile"
cp "$SCRIPT_DIR/docker-entrypoint.sh" "$BUILD_CONTEXT/"

echo "Building Docker image..."
cd "$BUILD_CONTEXT"
sudo docker build -t mysql-lineairdb:8.0.32 .

echo ""
echo "=== Build Complete ==="
echo "Docker image: mysql-lineairdb:8.0.32"
echo ""
echo "To verify the image:"
echo "  sudo docker run --rm mysql-lineairdb:8.0.32 mysqld --version"
echo ""
echo "To use with the cluster, run:"
echo "  cd $SCRIPT_DIR"
echo "  sudo docker-compose -f docker-compose-lineairdb.yml up -d"

