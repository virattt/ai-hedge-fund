#!/bin/bash

#activate poetry environment
if command -v poetry &> /dev/null; then
    echo "Using Poetry to run streamlit app."
    # Making sure dependancies are installed, and run the app
    poetry run streamlit run app.py
else
    #If Poetry is not installed, fall back to regular python script
    echo "Poetry is not found, using regular Python command line"

    #Install dependacies from requirements.txt file
    pip install -r requirements.txt && streamlit run app.py
fi

