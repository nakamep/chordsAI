#!/bin/bash
set -e # Exit immediately if a command exits with a non-zero status.

echo "Starting custom build process..."

# Upgrade pip and install setuptools and wheel first for good measure
pip install --upgrade pip setuptools wheel

echo "Installing Cython and NumPy first..."
pip install Cython numpy --no-cache-dir # --no-cache-dir can sometimes help with fresher installs

echo "Installing other dependencies from requirements.txt..."
pip install --no-build-isolation -r requirements.txt --no-cache-dir

echo "Build process completed."
