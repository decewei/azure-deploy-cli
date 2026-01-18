#!/bin/bash

ENV_DIR=".venv"

while [[ "$#" -gt 0 ]]; do
    case $1 in
        -i|--install) INSTALL_DEPS=true ;;
        *) echo "Unknown parameter: $1"; exit 1 ;;
    esac
    shift
done

# Create virtual environment with uv (Python 3.11 specified)
if [ ! -d "$ENV_DIR" ]; then
    echo "Creating virtual environment '$ENV_DIR' with uv..."
    uv venv -p 3.11 "$ENV_DIR"
    echo "Created virtual env $ENV_DIR"
fi

# Activate the virtual environment
source "$ENV_DIR/bin/activate"

if [ "$INSTALL_DEPS" = true ]; then
    echo "Installing dependencies with uv..."
    uv sync --all-extras
fi

echo "Type \`deactivate\` to exit the virtual environment."
