# rag/Dockerfile (minimal)
FROM python:3.11-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1 PYTHONPATH=/app

# system deps for psycopg2 and build tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev gcc curl ca-certificates \
  && rm -rf /var/lib/apt/lists/*

# copy only what the rag service needs
# if rag has its own requirements file, use it; otherwise use ../requirements.txt
COPY rag/ /app/rag/
COPY requirements.txt /tmp/requirements.txt

RUN pip install --no-cache-dir -r /tmp/requirements.txt

EXPOSE 8010

CMD ["uvicorn", "rag.rag_service_serve:app", "--host", "0.0.0.0", "--port", "8010"]
