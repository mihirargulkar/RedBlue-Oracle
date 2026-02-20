#!/bin/bash

# This script renames the current directory to GreenLine-Oracle
# Usage: ./rename_project.sh

PARENT_DIR=$(dirname "$(pwd)")
NEW_NAME="GreenLine-Oracle"

echo "Attempting to rename repository directory to $NEW_NAME..."

if mv "$(pwd)" "$PARENT_DIR/$NEW_NAME"; then
    echo "Successfully renamed to $NEW_NAME"
    echo "Please reload your workspace or 'cd' into the new directory."
else
    echo "Failed to rename directory. You may need to do this manually."
fi
