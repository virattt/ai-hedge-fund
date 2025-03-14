#!/bin/bash

# Activate poetry environment if it exists
if command -v poetry &> /dev/null; then
    echo "Using Poetry to run Streamlit app..."
    # Make sure dependencies are installed
    poetry install
    # Run the app
    poetry run streamlit run app.py
else
    # Fall back to regular Python if Poetry is not installed
    echo "Poetry not found, using regular Python..."
    # Install dependencies
    pip install -r requirements.txt
    # Run the app
    streamlit run app.py
fi 