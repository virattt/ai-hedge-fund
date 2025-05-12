#!/bin/bash
# test_model_param.sh - A script to test the model parameter fix

# Run with the model parameter to ensure it works
echo "Testing with model parameter..."
./run.sh --ticker AAPL --model deepseek-coder:r1 --ollama main --show-reasoning
