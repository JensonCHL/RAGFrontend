# Use a Node.js runtime as the base image
FROM node:20-alpine

# Set the working directory in the container
WORKDIR /app

# --- Add Debian repositories and install debug tools ---
RUN echo "deb http://deb.debian.org/debian bookworm main contrib non-free non-free-firmware" > /etc/apt/sources.list && \
    echo "deb http://security.debian.org/debian-security bookworm-security main contrib non-free non-free-firmware" >> /etc/apt/sources.list && \
    echo "deb http://deb.debian.org/debian bookworm-updates main contrib non-free non-free-firmware" >> /etc/apt/sources.list && \
    apt-get update && \
    apt-get install -y curl procps && \
    rm -rf /var/lib/apt/lists/*

# Copy package.json and package-lock.json
COPY package*.json ./

# Install dependencies
RUN npm install

# Expose the port the app runs on
EXPOSE 3000

# Command to start the development server
CMD ["npm", "run", "dev"]
