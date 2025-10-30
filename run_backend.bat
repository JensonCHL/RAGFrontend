#!/bin/bash
# Script to run the Flask backend

echo "Starting Flask backend server..."
cd backend
pip install -r requirements.txt
python app.py