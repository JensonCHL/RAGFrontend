# Docker Deployment Guide

## Overview

This RAG application uses Docker Compose to orchestrate 4 services:

1. **PostgreSQL** - Database
2. **Backend** - Main FastAPI backend (`BackendFastapi.py`)
3. **API Gateway** - n8n integration API (`n8n_API_fastapi.py`)
4. **Frontend** - Next.js web interface

## Architecture

```
┌─────────────┐
│  Frontend   │ :3000
│  (Next.js)  │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ API Gateway │ :5000
│  (FastAPI)  │
└──────┬──────┘
       │
       ▼
┌─────────────┐      ┌──────────────┐
│   Backend   │◄─────┤  PostgreSQL  │
│  (FastAPI)  │ :5001│              │ :5432
└──────┬──────┘      └──────────────┘
       │
       ▼
┌─────────────────────────────┐
│  Mounted Volumes            │
│  • /knowledge (PDFs)        │
│  • /ocr_cache (JSON cache)  │
│  • processing_states.json   │
└─────────────────────────────┘
```

## Volume Mounting Strategy

### What Gets Mounted

✅ **Data Directories** (Persisted across container restarts):

- `./knowledge` → PDF files uploaded by users
- `./backend/ocr_cache` → OCR cache JSON files
- `./processing_states.json` → Document processing state
- `./document_processing_log.json` → Processing logs

✅ **Source Code** (Development only):

- `./backend` → Backend Python code (hot-reload)
- `.` → Frontend code (hot-reload)

### Why This Approach?

1. **Persistence**: Data survives container restarts and rebuilds
2. **Shared State**: All containers access the same files
3. **Development**: Code changes reflect immediately without rebuilding
4. **Backup**: Easy to backup just the mounted directories
5. **Portability**: Same data works across different environments

## Docker Images Purpose

The Docker images provide:

- **Runtime Environment**: Python 3.11, Node.js 20, system dependencies
- **Isolated Processes**: Each service runs independently
- **Reproducibility**: Same setup on any machine
- **Scalability**: Can scale services independently

## Quick Start

### Development Mode

```bash
# Start all services with hot-reload
docker-compose -f docker-compose.dev.yml up -d

# View logs
docker-compose -f docker-compose.dev.yml logs -f

# Stop all services
docker-compose -f docker-compose.dev.yml down

# Rebuild after dependency changes
docker-compose -f docker-compose.dev.yml up -d --build
```

### Production Mode

```bash
# Build and start all services
docker-compose -f docker-compose.prod.yml up -d

# View logs
docker-compose -f docker-compose.prod.yml logs -f

# Stop all services
docker-compose -f docker-compose.prod.yml down
```

## Service URLs

- **Frontend**: http://localhost:3000
- **API Gateway**: http://localhost:5000
- **Backend**: http://localhost:5001
- **PostgreSQL**: localhost:5432

## Environment Variables

Create a `.env` file in the root directory with:

```env
# Database
DB_NAME=your_db_name
DB_USER=your_db_user
DB_PASSWORD=your_db_password
DB_HOST=postgres
DB_PORT=5432

# API Keys
OPENAI_API_KEY=your_openai_key
GEMINI_API_KEY=your_gemini_key

# Other configuration
NEXT_PUBLIC_API_URL=http://localhost:5000
```

## Common Commands

### View Service Status

```bash
docker-compose -f docker-compose.dev.yml ps
```

### Restart a Single Service

```bash
docker-compose -f docker-compose.dev.yml restart backend
```

### View Service Logs

```bash
# All services
docker-compose -f docker-compose.dev.yml logs -f

# Specific service
docker-compose -f docker-compose.dev.yml logs -f backend
```

### Execute Commands in Container

```bash
# Access backend shell
docker-compose -f docker-compose.dev.yml exec backend bash

# Run Python script
docker-compose -f docker-compose.dev.yml exec backend python manual_indexer.py
```

### Clean Up Everything

```bash
# Stop and remove containers, networks
docker-compose -f docker-compose.dev.yml down

# Also remove volumes (⚠️ deletes database data)
docker-compose -f docker-compose.dev.yml down -v
```

## Troubleshooting

### Port Already in Use

```bash
# Find process using port
netstat -ano | findstr :3000

# Kill process (Windows)
taskkill /PID <PID> /F
```

### Container Won't Start

```bash
# Check logs
docker-compose -f docker-compose.dev.yml logs backend

# Rebuild container
docker-compose -f docker-compose.dev.yml up -d --build backend
```

### Database Connection Issues

```bash
# Check if PostgreSQL is healthy
docker-compose -f docker-compose.dev.yml ps

# Restart PostgreSQL
docker-compose -f docker-compose.dev.yml restart postgres
```

### Permission Issues (Linux/Mac)

```bash
# Fix ownership of mounted volumes
sudo chown -R $USER:$USER ./knowledge ./backend/ocr_cache
```

## Best Practices

### Development

1. Use `docker-compose.dev.yml` for development
2. Source code is mounted for hot-reload
3. Make changes directly in your IDE
4. Containers automatically reflect changes

### Production

1. Use `docker-compose.prod.yml` for production
2. Source code is baked into images (more secure)
3. Only data directories are mounted
4. Rebuild images after code changes

### Data Backup

```bash
# Backup knowledge directory
tar -czf knowledge-backup-$(date +%Y%m%d).tar.gz ./knowledge

# Backup OCR cache
tar -czf ocr-cache-backup-$(date +%Y%m%d).tar.gz ./backend/ocr_cache

# Backup database
docker-compose -f docker-compose.dev.yml exec postgres pg_dump -U ${DB_USER} ${DB_NAME} > backup.sql
```

### Scaling

```bash
# Scale backend to 3 instances
docker-compose -f docker-compose.prod.yml up -d --scale backend=3
```

## Development vs Production

| Aspect         | Development          | Production         |
| -------------- | -------------------- | ------------------ |
| Source Code    | Mounted (hot-reload) | Baked into image   |
| Node Modules   | Anonymous volume     | Baked into image   |
| Restart Policy | `no`                 | `always`           |
| Health Checks  | Enabled              | Enabled            |
| Logging        | Verbose              | Standard           |
| Build Time     | Fast (cached)        | Slower (optimized) |

## Migration from Local Development

If you're currently running:

```bash
npm run dev          # Frontend
python BackendFastapi.py      # Backend
python n8n_API_fastapi.py     # API Gateway
```

Switch to Docker:

```bash
docker-compose -f docker-compose.dev.yml up -d
```

Your data in `/knowledge` and `/backend/ocr_cache` will work seamlessly!
