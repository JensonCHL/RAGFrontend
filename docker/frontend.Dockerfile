# Use a Node.js runtime as the base image
FROM node:20-alpine

# Set the working directory in the container
WORKDIR /app
# Copy package.json and package-lock.json
COPY package*.json ./

# Install dependencies
RUN npm install

# Expose the port the app runs on
EXPOSE 3000

# Command to start the development server
CMD ["npm", "run", "dev"]
