# Use an official Python runtime as a parent image
FROM python:3.10-slim

# Set the working directory in the container
WORKDIR /app

# Copy the backend requirements file and install dependencies
# The API Gateway uses the same requirements as the main backend
COPY ./backend/requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Expose the port the app runs on
EXPOSE 5000

# Define the command to run the Flask development server
CMD ["flask", "run", "--host=0.0.0.0", "--port=5000"]
