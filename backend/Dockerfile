FROM python:3.12-slim AS builder
WORKDIR /app
COPY pyproject.toml .
RUN pip install --no-cache-dir .

FROM python:3.12-slim AS runtime
WORKDIR /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        curl gnupg unixodbc unixodbc-dev && \
    curl -fsSL https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor -o /usr/share/keyrings/microsoft-prod.gpg && \
    curl -fsSL https://packages.microsoft.com/config/debian/12/prod.list | \
        sed 's|deb \[signed-by=/etc/apt/keyrings/microsoft.gpg]|deb [signed-by=/usr/share/keyrings/microsoft-prod.gpg]|' \
        > /etc/apt/sources.list.d/mssql-release.list && \
    apt-get update && \
    ACCEPT_EULA=Y apt-get install -y --no-install-recommends msodbcsql18 && \
    rm -rf /var/lib/apt/lists/*
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY . .
ENV PYTHONPATH=/app
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
  CMD python -c "import http.client; c=http.client.HTTPConnection('localhost',8000); c.request('GET','/health'); r=c.getresponse(); assert r.status==200, f'status={r.status}'; r.read(); c.close()"
CMD ["uvicorn", "qdata.web.main:app", "--host", "0.0.0.0", "--port", "8000"]
