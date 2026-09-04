FROM python:3.11-slim

WORKDIR /app

# Set Python to run in unbuffered mode for real-time console output
ENV PYTHONUNBUFFERED=1

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Create dedicated directory for persistent SQLite storage
RUN mkdir -p /data
VOLUME ["/data"]

# Default container database path pointing to persistent volume
ENV TRAINING_CLIENT_DB_PATH=/data/training.db

# Copy application source code
COPY . .

CMD ["python", "main.py"]