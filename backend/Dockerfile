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

RUN apt-get update && \
    apt-get install -y --no-install-recommends unzip && \
    curl -fsSL http://ftp.debian.org/debian/pool/main/liba/libaio/libaio1_0.3.113-4_amd64.deb -o /tmp/libaio.deb && \
    dpkg-deb -x /tmp/libaio.deb /tmp/libaio && \
    cp /tmp/libaio/usr/lib/x86_64-linux-gnu/libaio.so.1* /usr/lib/x86_64-linux-gnu/ && \
    rm -rf /tmp/libaio /tmp/libaio.deb && \
    curl -fsSL https://download.oracle.com/otn_software/linux/instantclient/instantclient-basiclite-linuxx64.zip -o /tmp/instantclient.zip && \
    unzip -q /tmp/instantclient.zip -d /opt/oracle && \
    rm /tmp/instantclient.zip && \
    for d in /opt/oracle/instantclient_*; do mv "$d" /opt/oracle/instantclient; break; done && \
    rm -rf /var/lib/apt/lists/*

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        rpm bc default-jre-headless \
        libcrypt1 libpam0g libstdc++6 libncurses6 libelf1t64 && \
    mkdir -p /var/lib/rpm && \
    rpm --initdb && \
    rm -rf /var/lib/apt/lists/*

COPY clientsdk.tar /tmp/clientsdk.tar
RUN mkdir -p /tmp/csdk && tar -xf /tmp/clientsdk.tar -C /tmp/csdk && \
    cd /tmp/csdk && chmod +x installclientsdk && \
    { printf '\n1\n'; yes "" | head -n 5000; } | ./installclientsdk -DPRQCHECK=FALSE -DLICENSE_ACCEPTED=TRUE -DUSER_INSTALL_DIR=/opt/IBM/informix -DCHOSEN_FEATURE_LIST=SDK,SDK-ODBC,GLS,GLS-WEURAM -DCHOSEN_INSTALL_FEATURE_LIST=SDK,SDK-ODBC,GLS,GLS-WEURAM -DCHOSEN_INSTALL_SET=Custom; \
    printf "[Informix]\nDescription=IBM Informix ODBC Driver\nDriver=/opt/IBM/informix/lib/cli/iclit09b.so\nSetup=/opt/IBM/informix/lib/cli/iclit09b.so\n" >> /etc/odbcinst.ini && \
    printf "\n[InformixDM]\nDescription=IBM Informix ODBC Driver Manager\nDriver=/opt/IBM/informix/lib/cli/idmrs09a.so\nSetup=/opt/IBM/informix/lib/cli/idmrs09a.so\n" >> /etc/odbcinst.ini && \
    rm -rf /tmp/clientsdk.tar /tmp/csdk

COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY qdata/ /app/qdata/
COPY alembic/ /app/alembic/
COPY alembic.ini /app/
COPY pyproject.toml /app/
ENV PYTHONPATH=/app
ENV INFORMIXDIR=/opt/IBM/informix
ENV LD_LIBRARY_PATH=/opt/IBM/informix/lib/cli:/opt/IBM/informix/lib/esql:/opt/oracle/instantclient
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
  CMD python -c "import http.client; c=http.client.HTTPConnection('localhost',8000); c.request('GET','/health'); r=c.getresponse(); assert r.status==200, f'status={r.status}'; r.read(); c.close()"
CMD ["uvicorn", "qdata.web.main:app", "--host", "0.0.0.0", "--port", "8000"]
