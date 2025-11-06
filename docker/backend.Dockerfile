# Use an official Python runtime as a parent image
FROM python:3.10-slim

# Set the working directory in the container
WORKDIR /app

# Copy the backend requirements file and install dependencies
COPY ./backend/requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the backend source code - This is now handled by a volume mount in docker-compose for development
# COPY ./backend /app/

# The .env file should not be copied into the image.
# It will be provided at runtime via docker-compose.

# Expose the port the app runs on
EXPOSE 5001

# Define the command to run the Flask development server
# The --host=0.0.0.0 flag makes it accessible from outside the container
CMD ["flask", "run", "--host=0.0.0.0", "--port=5001"]
