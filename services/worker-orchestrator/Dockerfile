FROM python:3.12-slim

WORKDIR /app

# Install shared package
COPY packages/shared /tmp/shared
RUN pip install --no-cache-dir /tmp/shared && rm -rf /tmp/shared

# Install service dependencies
COPY services/worker-orchestrator/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY services/worker-orchestrator/ .

CMD ["python", "-m", "app.main"]
