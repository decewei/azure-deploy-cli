#!/bin/bash

# Default environment name
ENV_NAME="azure-deploy-cli"

while [[ "$#" -gt 0 ]]; do
    case $1 in
        -n|--name) ENV_NAME="$2"; shift ;;
        -i|--install) INSTALL_DEPS=true ;;
        *) echo "Unknown parameter: $1"; exit 1 ;;
    esac
    shift
done

# Check if the script is being sourced
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    echo "Error: This script must be sourced, not executed directly."
    echo "Please run it as: source setup.sh"
    exit 1
fi

# Check if the virtual environment is already activated
if [[ "$VIRTUAL_ENV" != "" ]]
then
    echo "Virtual environment is already activated."
else
    # Create a virtual environment if it doesn't exist
    if [ ! -d "$ENV_NAME" ]; then
        echo "Creating virtual environment '$ENV_NAME'..."
        python3 -m venv "$ENV_NAME"
        echo "Created virtual env $VIRTUAL_ENV"
    fi

    # Activate the virtual environment
    echo "Activating virtual environment '$ENV_NAME'..."
    # The key part: sourcing to keep it in the current shell
    source "$ENV_NAME/bin/activate"

    # Check if activation worked
    if [[ "$VIRTUAL_ENV" == "" ]]; then
        echo "Failed to activate virtual environment!"
        exit 1
    fi
fi

if [ "$INSTALL_DEPS" = true ]; then
    echo "Installing dependencies..."
    pip install --upgrade pip
    make install-dev
fi

echo "Type \`deactivate\` to exit the virtual environment."
