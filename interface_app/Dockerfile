# interface_app/Dockerfile (minimal)
FROM python:3.11-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1

# system deps for psycopg2
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev gcc && \
    rm -rf /var/lib/apt/lists/*

# copy and install requirements
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# copy only the interface app
COPY interface_app/ /app/interface_app/

EXPOSE 8501

# pass address/port via flags (no extra STREAMLIT env needed)
CMD ["streamlit", "run", "interface_app/app.py", "--server.port=8501", "--server.address=0.0.0.0"]
