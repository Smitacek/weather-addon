ARG BUILD_FROM=ghcr.io/home-assistant/amd64-base-python:3.11-alpine3.18
FROM $BUILD_FROM

RUN apk add --no-cache \
    gcc \
    musl-dev \
    linux-headers

WORKDIR /app

COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

COPY main.py .
COPY mqtt_listener.py .
COPY web ./web
COPY run.sh /
RUN chmod a+x /run.sh

CMD ["python3", "/app/main.py"]

