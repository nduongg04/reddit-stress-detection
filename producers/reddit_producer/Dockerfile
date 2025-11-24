FROM python:3.9-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy producer code
COPY . .

# Set environment for Kafka connection
ENV PYTHONUNBUFFERED=1

CMD ["python", "main.py"]
