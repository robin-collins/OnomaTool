#!/bin/bash
set -e

echo "Testing Onomatool installation..."

# Ensure uv is available
if ! command -v uv &> /dev/null; then
    echo "Error: uv is required. Install it: curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 1
fi

# Build the package first if dist/ doesn't exist
if [ ! -d "dist" ] || [ -z "$(ls dist/*.whl 2>/dev/null)" ]; then
    echo "Building package first..."
    uv build
fi

# Test the CLI command via uvx with the built wheel
echo "Testing CLI via uvx with built wheel..."
WHL=$(ls dist/*.whl | head -1)
uvx --from "$WHL" onomatool --help

# Test basic functionality with mock provider
echo "Testing basic functionality..."
TEMP_DIR=$(mktemp -d)
echo "This is a test file for onomatool" > "$TEMP_DIR/test_file.txt"

cat > "$TEMP_DIR/test_config.toml" << EOF
default_provider = "mock"
naming_convention = "snake_case"
EOF

# Test dry run
uvx --from "$WHL" onomatool --config "$TEMP_DIR/test_config.toml" --dry-run "$TEMP_DIR/*.txt"

# Cleanup
echo "Cleaning up..."
rm -rf "$TEMP_DIR"

echo "Installation test passed!"
