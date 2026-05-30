FROM python:3.12-slim

WORKDIR /app

# Install shared package
COPY packages/shared /tmp/shared
RUN pip install --no-cache-dir /tmp/shared && rm -rf /tmp/shared

# Install service dependencies
COPY services/api/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY services/api/ .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

# redeploy 2026-05-27: ship change-only metrics storage (fd8e0a3) + miner refactors
# stuck behind the GitHub Actions billing block; first deploy since 05-24.
