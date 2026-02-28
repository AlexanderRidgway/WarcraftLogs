FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1

# Install AWS CLI for entrypoint secret fetching
RUN pip install --no-cache-dir awscli

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code and default config
COPY src/ src/
COPY config.yaml .
COPY entrypoint.sh .
RUN chmod +x entrypoint.sh

ENTRYPOINT ["./entrypoint.sh"]
