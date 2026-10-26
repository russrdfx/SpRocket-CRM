FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
ENV PIP_CERT=/etc/ssl/certs/ca-certificates.crt
WORKDIR /app
# Refresh outbound HTTPS trust independently of the base image's build date.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates \
    && update-ca-certificates \
    && dpkg-query -W ca-certificates \
    && rm -rf /var/lib/apt/lists/*
COPY deploy/verify_https_trust.py ./deploy/verify_https_trust.py
RUN python deploy/verify_https_trust.py
COPY requirements.txt requirements-web.txt ./
RUN python -m pip install --no-cache-dir --upgrade 'pip>=26.2.2' \
    && python -m pip install --no-cache-dir -r requirements-web.txt \
    && useradd --create-home --uid 10001 sprocket
COPY *.py ./
COPY web ./web
COPY deploy/gunicorn.conf.py ./deploy/gunicorn.conf.py
RUN mkdir /app/data && chown -R sprocket:sprocket /app/data
USER sprocket
EXPOSE 8000
CMD ["gunicorn","-c","deploy/gunicorn.conf.py","web_server:application"]
