#!/bin/bash
# Package Lambda function for deployment

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
LAMBDA_DIR="$PROJECT_ROOT/lambda"
BUILD_DIR="$LAMBDA_DIR/build"
PACKAGE_DIR="$BUILD_DIR/package"

echo "Packaging Lambda function..."

# Clean previous build
rm -rf "$BUILD_DIR"
mkdir -p "$PACKAGE_DIR"

# Install dependencies
echo "Installing dependencies..."
pip install -r "$LAMBDA_DIR/requirements.txt" -t "$PACKAGE_DIR" --quiet

# Copy source code
echo "Copying source code..."
cp -r "$PROJECT_ROOT/src" "$PACKAGE_DIR/"
cp "$LAMBDA_DIR/handler.py" "$PACKAGE_DIR/"

# Remove unnecessary files to reduce size
echo "Cleaning up..."
find "$PACKAGE_DIR" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find "$PACKAGE_DIR" -type d -name "*.dist-info" -exec rm -rf {} + 2>/dev/null || true
find "$PACKAGE_DIR" -type d -name "tests" -exec rm -rf {} + 2>/dev/null || true
find "$PACKAGE_DIR" -name "*.pyc" -delete 2>/dev/null || true

# Create zip file
echo "Creating zip file..."
cd "$PACKAGE_DIR"
zip -r "$BUILD_DIR/lambda_function.zip" . -q

# Show size
SIZE=$(du -h "$BUILD_DIR/lambda_function.zip" | cut -f1)
echo ""
echo "Package created: $BUILD_DIR/lambda_function.zip"
echo "Size: $SIZE"
echo ""
echo "To deploy via AWS CLI:"
echo "  aws lambda update-function-code --function-name nhtsa-recall-analyzer --zip-file fileb://$BUILD_DIR/lambda_function.zip"
