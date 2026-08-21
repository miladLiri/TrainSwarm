FROM python:3.11-slim

WORKDIR /app

# Set Python to run in unbuffered mode for real-time console output
ENV PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "main.py"]