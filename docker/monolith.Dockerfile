FROM node:20-alpine

# Install Python and dependencies
RUN apk add --no-cache \
    python3 \
    py3-pip \
    postgresql-client \
    curl \
    bash \
    libffi-dev \
    openssl-dev \
    python3-dev \
    musl-dev \
    gcc \
    postgresql-dev

# Create symlink for python -> python3
RUN ln -sf python3 /usr/bin/python

# Upgrade pip
RUN python -m pip install --upgrade pip

# Install Python packages directly without virtual environment
RUN python -m pip install --break-system-packages flask qdrant-client python-dotenv flask-cors openai PyMuPDF Pillow langchain-openai psycopg2-binary gunicorn PyJWT requests

# Set up working directory
WORKDIR /app

# Copy and install Node.js dependencies
COPY package*.json ./
RUN npm install

# Copy all source code
COPY . .

# Build Next.js app
RUN npm run build

# Create directories for data persistence
RUN mkdir -p /app/knowledge /app/backend/ocr_cache /app/backend/processing_logs

# Expose ports
EXPOSE 3000 5000 5001 5432

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:3000/api/health || exit 1

# Start script
COPY docker/start-services.sh /start-services.sh
RUN chmod +x /start-services.sh

CMD ["/start-services.sh"]