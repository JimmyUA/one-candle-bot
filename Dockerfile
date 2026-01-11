# Use Python slim image for smaller size
FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY config.py .
COPY quick_flip_scalper.py .
COPY main.py .

# Cloud Run uses PORT environment variable
ENV PORT=8080

# Run the application with --immediate flag for Cloud Run triggered execution
ENTRYPOINT ["python", "main.py", "--immediate"]
