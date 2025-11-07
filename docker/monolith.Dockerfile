FROM node:20-alpine

# Install Python, PostgreSQL client, and other dependencies
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

# Set up working directory
WORKDIR /app

# Create and activate virtual environment
RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
ENV VIRTUAL_ENV="/opt/venv"

# Upgrade pip
RUN pip install --upgrade pip

# Copy and install Python dependencies first (for backend services)
COPY backend/requirements.txt ./backend/
RUN pip install --no-cache-dir --break-system-packages -r backend/requirements.txt

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