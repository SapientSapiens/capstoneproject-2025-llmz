FROM python:3.11-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1 PYTHONPATH=/app

# system deps for psycopg2 and build tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev gcc curl ca-certificates \
  && rm -rf /var/lib/apt/lists/*

# copy and install requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# copy the rag service
COPY . .

EXPOSE 8010

CMD ["uvicorn", "rag_service_serve:app", "--host", "0.0.0.0", "--port", "8010"]