FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Fix file paths for containerized environment
RUN sed -i 's|../reports/grid_plots|/app/reports/grid_plots|g' web/app.py

# Expose port
EXPOSE 8000

# Set environment variables
ENV FLASK_HOST=0.0.0.0
ENV FLASK_PORT=8000

# Run the Flask application
CMD ["python", "web/app.py"]