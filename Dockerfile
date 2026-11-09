FROM python:3.12-slim
LABEL description="Local Anonymizer v4 — Local clinical anonymization tool"
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# Usuari sense privilegis: l'app només llegeix el seu codi i treballa en memòria
RUN useradd --create-home --uid 10001 app
COPY app/     ./app/
COPY static/  ./static/
COPY sample_data/ ./sample_data/
USER app
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=4)"
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
