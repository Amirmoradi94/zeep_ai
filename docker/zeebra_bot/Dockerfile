# Use a lightweight Python image
FROM python:3.10-slim

# Set the working directory inside the container
WORKDIR /app

ENV PYTHONUNBUFFERED=TRUE

# Install system dependencies, including FFmpeg
RUN apt-get update && \
    apt-get install -y \
    ffmpeg \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements.txt and install Python dependencies
COPY ./zeebra_bot/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY ./zeebra_bot /app

# Create necessary directories
RUN mkdir -p /app/logs /app/reels /app/saved_images

# Set the entry point for the bot using Gunicorn
CMD ["gunicorn", "--workers", "4", "--worker-class", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:5000", "zeebra_main:app"]

