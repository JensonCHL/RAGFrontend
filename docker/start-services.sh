#!/bin/bash

# Start PostgreSQL in the background
echo "Starting PostgreSQL..."
mkdir -p /var/lib/postgresql/data
chmod 700 /var/lib/postgresql/data
chown -R postgres:postgres /var/lib/postgresql
su - postgres -c "pg_ctl -D /var/lib/postgresql/data -l /tmp/postgres.log start" &

# Wait for PostgreSQL to start
echo "Waiting for PostgreSQL to start..."
until su - postgres -c "pg_isready" > /dev/null 2>&1; do
  sleep 1
done
echo "PostgreSQL started!"

# Create database and user if they don't exist
echo "Setting up database..."
su - postgres -c "psql -c \"CREATE USER postgres WITH PASSWORD 'Cloudeka12345';\" 2>/dev/null || true"
su - postgres -c "psql -c \"CREATE DATABASE postgres OWNER postgres;\" 2>/dev/null || true"
su - postgres -c "psql -c \"GRANT ALL PRIVILEGES ON DATABASE postgres TO postgres;\" 2>/dev/null || true"

# Start backend service
echo "Starting Backend service..."
export FLASK_APP=app.py
export FLASK_DEBUG=1
python3 backend/app.py &

# Start API gateway service
echo "Starting API Gateway service..."
export FLASK_APP=n8n_API.py
export FLASK_DEBUG=1
python3 backend/n8n_API.py &

# Start frontend service
echo "Starting Frontend service..."
npm run dev &

# Wait for all services
echo "All services started!"
echo "Frontend: http://localhost:3000"
echo "API Gateway: http://localhost:5000"
echo "Backend: http://localhost:5001"
echo "PostgreSQL: localhost:5432"

# Keep container running
wait