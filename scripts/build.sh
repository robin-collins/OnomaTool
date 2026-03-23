#!/bin/bash
set -e

echo "Building Onomatool package..."

# Ensure uv is available
if ! command -v uv &> /dev/null; then
    echo "Error: uv is required. Install it: curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 1
fi

# Clean previous builds
echo "Cleaning previous builds..."
rm -rf dist/ build/ src/onomatool.egg-info/

# Sync dependencies
echo "Syncing dependencies..."
uv sync --all-extras

# Run linting and formatting
echo "Running code quality checks..."
uv run ruff check src/
uv run ruff format src/

# Build the package
echo "Building package..."
uv build

# Verify the package
echo "Verifying package..."
uv run twine check dist/* 2>/dev/null || echo "Note: install twine for package verification (uv pip install twine)"

echo "Build complete! Distribution files:"
ls -la dist/

echo ""
echo "To publish to PyPI:"
echo "  Test PyPI: uv run twine upload --repository testpypi dist/*"
echo "  Real PyPI: uv run twine upload dist/*"
echo ""
echo "To test with uvx:"
echo "  uvx --from ./dist/onomatool-*.whl onomatool --help"
