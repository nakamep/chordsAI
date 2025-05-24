#!/bin/bash
set -e # Exit immediately if a command exits with a non-zero status.

echo "Starting build process..."

# Upgrade pip and install setuptools and wheel first for good measure
pip install --upgrade pip setuptools wheel

echo "Installing dependencies from requirements.txt..."
pip install -r requirements.txt --no-cache-dir # Removed --no-build-isolation

echo "Build process completed."
