FROM python:3.11-slim

WORKDIR /app

# Set Python to run in unbuffered mode for real-time console output
ENV PYTHONUNBUFFERED=1

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Create dedicated directories for persistent SQLite storage and artifacts
RUN mkdir -p /data /artifacts
VOLUME ["/data", "/artifacts"]

# Default container paths pointing to persistent volumes
ENV TRAINING_CLIENT_DB_PATH=/data/training.db
ENV TRAINING_WORKING_DIRECTORY=/artifacts
ENV TRAINING_CLIENT_WORKING_DIRECTORY=/artifacts

# Copy application source code
COPY . .

CMD ["python", "main.py"]