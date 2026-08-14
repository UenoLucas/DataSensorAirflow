FROM python:3.10-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/opt/project

WORKDIR /opt/project

COPY requirements-app.txt /tmp/requirements-app.txt

RUN pip install \
    --no-cache-dir \
    -r /tmp/requirements-app.txt

COPY controllers ./controllers
COPY models ./models
COPY scripts ./scripts
COPY dashboard ./dashboard

CMD ["python", "scripts/SubscriberMqtt.py"]