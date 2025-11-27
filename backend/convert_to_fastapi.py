"""
FastAPI Conversion Script
Converts app.py (Flask) to app_fastapi.py (FastAPI)
"""

import re

# Read the Flask app
with open('app.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Replace imports
content = content.replace(
    'from flask import Flask, jsonify, request, stream_with_context, Response, send_file',
    'from fastapi import FastAPI, Request, Query, BackgroundTasks, UploadFile, File, Form\n'
    'from fastapi.responses import JSONResponse, StreamingResponse, FileResponse'
)
content = content.replace('from flask_cors import CORS', 'from fastapi.middleware.cors import CORSMiddleware')
content = content.replace('from pydantic import BaseModel', '')
content = 'from pydantic import BaseModel\n' + content

# Replace app initialization
content = content.replace(
    'app = Flask(__name__)\nCORS(app)  # Enable CORS for all routes',
    '''app = FastAPI(
    title="RAG System API",
    description="Document processing and management API",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)'''
)

# Convert Flask routes to FastAPI
# Pattern: @app.route('/path', methods=['GET'])
# To: @app.get("/path")

# GET routes
content = re.sub(
    r"@app\.route\('([^']+)',\s*methods=\['GET'\]\)",
    r'@app.get("\1")',
    content
)

# POST routes
content = re.sub(
    r"@app\.route\('([^']+)',\s*methods=\['POST'\]\)",
    r'@app.post("\1")',
    content
)

# DELETE routes
content = re.sub(
    r"@app\.route\('([^']+)',\s*methods=\['DELETE'\]\)",
    r'@app.delete("\1")',
    content
)

# Convert function signatures to async
content = re.sub(
    r'def (get_|create_|delete_|upload_|process_|list_)([a-z_]+)\(',
    r'async def \1\2(',
    content
)

# Convert jsonify to JSONResponse
content = content.replace('return jsonify(', 'return JSONResponse(')
content = content.replace('), 500', ', status_code=500)')
content = content.replace('), 400', ', status_code=400)')
content = content.replace('), 404', ', status_code=404)')
content = content.replace('), 201', ', status_code=201)')

# Convert request.get_json() to await request.json()
content = content.replace('request.get_json()', 'await request.json()')
content = content.replace('request.args.get(', 'Query(default=None, description=')
content = content.replace('request.files', 'files')

# Convert Response to StreamingResponse for SSE
content = content.replace(
    'return Response(event_stream(), mimetype="text/event-stream")',
    'return StreamingResponse(event_stream(), media_type="text/event-stream")'
)

# Convert send_file to FileResponse
content = content.replace('return send_file(', 'return FileResponse(')

# Add async to generator functions for streaming
content = re.sub(
    r'def event_stream\(\):',
    r'async def event_stream():',
    content
)

# Write the converted file
with open('app_fastapi.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("✅ Conversion complete! Created app_fastapi.py")
print("⚠️  Note: Manual review recommended for:")
print("   - Request body handling (may need Pydantic models)")
print("   - File uploads (need UploadFile type)")
print("   - Path parameters (need type hints)")
print("   - Query parameters (need Query() wrapper)")
