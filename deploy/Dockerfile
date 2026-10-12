FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt requirements-web.txt ./
RUN pip install --no-cache-dir -r requirements-web.txt && useradd --create-home --uid 10001 sprocket
COPY *.py ./
COPY web ./web
COPY deploy/gunicorn.conf.py ./deploy/gunicorn.conf.py
RUN mkdir /app/data && chown -R sprocket:sprocket /app/data
USER sprocket
EXPOSE 8000
CMD ["gunicorn","-c","deploy/gunicorn.conf.py","web_server:application"]
