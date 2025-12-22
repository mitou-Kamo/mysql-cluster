#!/bin/bash
# Build Script for Ubuntu MySQL Image for LineairDB Cluster
#
# Usage:
#   ./build-image.sh [OPTIONS]
#
# Options:
#   -t, --tag TAG       Image tag (default: mysql-lineairdb-ubuntu:8.0.43)
#   -v, --version VER   MySQL version (default: 8.0.43)
#   --no-cache          Build without cache
#   --push              Push to registry after build
#   -h, --help          Show this help message

set -e

# Default values
IMAGE_TAG="mysql-lineairdb-ubuntu:8.0.43"
MYSQL_VERSION="8.0.43"
NO_CACHE=""
PUSH_IMAGE=false

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -t|--tag)
            IMAGE_TAG="$2"
            shift 2
            ;;
        -v|--version)
            MYSQL_VERSION="$2"
            shift 2
            ;;
        --no-cache)
            NO_CACHE="--no-cache"
            shift
            ;;
        --push)
            PUSH_IMAGE=true
            shift
            ;;
        -h|--help)
            echo "Build Ubuntu MySQL Image for LineairDB Cluster"
            echo ""
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  -t, --tag TAG       Image tag (default: mysql-lineairdb-ubuntu:8.0.43)"
            echo "  -v, --version VER   MySQL version (default: 8.0.43)"
            echo "  --no-cache          Build without cache"
            echo "  --push              Push to registry after build"
            echo "  -h, --help          Show this help message"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

echo "============================================"
echo "Building Ubuntu MySQL Image for LineairDB"
echo "============================================"
echo "Image Tag: $IMAGE_TAG"
echo "MySQL Version: $MYSQL_VERSION"
echo "Script Directory: $SCRIPT_DIR"
echo "============================================"

# Check if Docker is available
if ! command -v docker &> /dev/null; then
    echo "ERROR: Docker is not installed or not in PATH"
    exit 1
fi

# Check if Dockerfile exists
if [ ! -f "$SCRIPT_DIR/Dockerfile.ubuntu" ]; then
    echo "ERROR: Dockerfile.ubuntu not found in $SCRIPT_DIR"
    exit 1
fi

# Check if entrypoint script exists
if [ ! -f "$SCRIPT_DIR/docker-entrypoint.sh" ]; then
    echo "ERROR: docker-entrypoint.sh not found in $SCRIPT_DIR"
    exit 1
fi

# Build the image
echo ""
echo "Building Docker image..."
docker build \
    $NO_CACHE \
    --build-arg MYSQL_VERSION="$MYSQL_VERSION" \
    -t "$IMAGE_TAG" \
    -f "$SCRIPT_DIR/Dockerfile.ubuntu" \
    "$SCRIPT_DIR"

echo ""
echo "Build completed successfully!"
echo "Image: $IMAGE_TAG"

# Show image info
docker images "$IMAGE_TAG"

# Push if requested
if [ "$PUSH_IMAGE" = true ]; then
    echo ""
    echo "Pushing image to registry..."
    docker push "$IMAGE_TAG"
    echo "Push completed!"
fi

echo ""
echo "============================================"
echo "To test the image:"
echo "  docker run -d --name mysql-test \\"
echo "    -e MYSQL_ROOT_PASSWORD=test123 \\"
echo "    -p 3307:3306 \\"
echo "    $IMAGE_TAG"
echo ""
echo "To use with mysql-cluster-bridge:"
echo "  mysql-cluster-bridge build-image"
echo "  mysql-cluster-bridge create --secondaries 3"
echo "============================================"

