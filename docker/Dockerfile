# Use official slim Python image
FROM python:3.10-slim

# Set working directory inside container
WORKDIR /app

# Install system dependencies (gcc, curl, etc)
RUN apt-get update && apt-get install -y build-essential curl && rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the entire Django project code
COPY . .

# Expose port 8000 (Render uses this port by default)
EXPOSE 8000

# Run Daphne ASGI server for Channels support
CMD ["daphne", "-b", "0.0.0.0", "-p", "8000", "your_project_name.asgi:application"]
