#!/bin/bash
# Build MySQL 8.0.43 image with LineairDB support

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
IMAGE_TAG="mysql-lineairdb-ubuntu:8.0.43"

echo "============================================"
echo "Building MySQL 8.0.43 + LineairDB Image"
echo "============================================"

# Copy required libraries from host Ubuntu system
echo "Copying required libraries from Ubuntu..."
cp /lib/x86_64-linux-gnu/libjemalloc.so.2 "$SCRIPT_DIR/"
cp /lib/x86_64-linux-gnu/libatomic.so.1 "$SCRIPT_DIR/"
cp /lib/x86_64-linux-gnu/libnuma.so.1 "$SCRIPT_DIR/"
cp /lib/x86_64-linux-gnu/libstdc++.so.6 "$SCRIPT_DIR/"

# Build the image
echo "Building Docker image..."
docker build -t "$IMAGE_TAG" -f "$SCRIPT_DIR/Dockerfile.ubuntu" "$SCRIPT_DIR"

# Clean up copied libraries
rm -f "$SCRIPT_DIR/libjemalloc.so.2" "$SCRIPT_DIR/libatomic.so.1" "$SCRIPT_DIR/libnuma.so.1" "$SCRIPT_DIR/libstdc++.so.6"

echo ""
echo "============================================"
echo "Build complete: $IMAGE_TAG"
echo "============================================"
