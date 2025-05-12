#!/bin/bash
# test_docker_imports.sh - A script to test the Python import path fix

echo "Building Docker image with updated PYTHONPATH..."
docker-compose build

echo "Running import test..."
docker-compose run --rm test-imports

echo "Test complete."
