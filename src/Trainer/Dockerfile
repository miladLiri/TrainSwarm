FROM python:3.11-slim

# Set working directory to /artifacts
WORKDIR /artifacts

# Set Python to run in unbuffered mode and configure PYTHONPATH
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app
ENV COORDINATOR_ADDRESS=http://coordinator:8080
ENV COORDINATOR_GRPC_ADDRESS=coordinator:8081
ENV TRAINER_WORKING_DIRECTORY=/artifacts
ENV WORKING_DIR=/artifacts
ENV P2P_GRPC_HOST=127.0.0.1
ENV P2P_GRPC_PORT=50051

# Install dependencies into /app
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy application source code into /app
COPY . /app/

# Declare /artifacts volume
VOLUME ["/artifacts"]

CMD ["python", "/app/main.py"]

