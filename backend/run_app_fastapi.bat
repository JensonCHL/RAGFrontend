@echo off
REM Install FastAPI app requirements and start the server

echo Installing FastAPI app requirements...
pip install -r requirements_fastapi_app.txt

echo Starting FastAPI app server...
uvicorn app_fastapi:app --host 0.0.0.0 --port 5001 --reload