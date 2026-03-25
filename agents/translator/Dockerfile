FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir httpx>=0.28.0

COPY agent.py config.json ./

ENV PYTHONUNBUFFERED=1

CMD ["python", "agent.py"]
