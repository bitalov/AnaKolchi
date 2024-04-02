#!/bin/bash

# Install Streamlit if not already installed
if ! command -v streamlit &> /dev/null
then
    echo "Streamlit not found, installing..."
    pip install streamlit
fi
pip install requirements.txt

# Run the Streamlit app
streamlit run main_AK.py  --server.port 8000 --server.address 0.0.0.0

