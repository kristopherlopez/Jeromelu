FROM python:3.12-slim

WORKDIR /app

# Install internal packages
COPY packages/shared /tmp/shared
RUN pip install --no-cache-dir /tmp/shared && rm -rf /tmp/shared
COPY packages/youtube /tmp/youtube
RUN pip install --no-cache-dir /tmp/youtube && rm -rf /tmp/youtube

# Install service dependencies
COPY services/worker-ingestion/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY services/worker-ingestion/ .

CMD ["python", "-m", "app.main"]
