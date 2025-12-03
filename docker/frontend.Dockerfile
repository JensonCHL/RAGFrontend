# Frontend Dockerfile for Next.js
FROM node:20-alpine

# Set working directory
WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm install

# Expose port
EXPOSE 3000

# Set environment variable to allow Next.js to bind to 0.0.0.0
ENV HOSTNAME=0.0.0.0

# Command to run the frontend in development mode
CMD ["npm", "run", "dev"]
