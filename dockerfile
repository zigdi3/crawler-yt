# Dockerfile
FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Env from Azure
ARG    YOUTUBE_API_KEY
# Set environment variables
ENV    PYTHONDONTWRITEBYTECODE=1 
ENV    PYTHONUNBUFFERED=1 
ENV    PORT=5000
ENV    YOUTUBE_API_KEY={YOUTUBE_API_KEY}

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements file
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY *.py .

# Expose the port the app runs on
EXPOSE ${PORT}

# Command to run the application
CMD ["sh", "-c", "python api.py"]