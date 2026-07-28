# Use an official lightweight Python image
FROM python:3.12-slim

# Set the working directory within the container
WORKDIR /app

# Ensure logs are not buffered so they appear immediately in Cloud Run logs
ENV PYTHONUNBUFFERED=1

# Prevent Python from writing .pyc bytecode files to save space
ENV PYTHONDONTWRITEBYTECODE=1

# Copy the requirements file first to leverage Docker cache
COPY requirements.txt .

# Install dependencies without keeping the cache directory
RUN pip install --no-cache-dir -r requirements.txt

# Copy the necessary application directories 
COPY src/ ./src/
COPY scripts/ ./scripts/
COPY data/ ./data/

# Cloud Run injects a PORT environment variable, which defaults to 8080
EXPOSE 8080

# Start the FastAPI application, binding it to the Cloud Run PORT variable
CMD ["sh", "-c", "uvicorn src.slack_server:app --host 0.0.0.0 --port ${PORT:-8080}"]