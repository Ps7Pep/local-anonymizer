FROM python:3.12-slim
LABEL description="Datathon Anonymizer v3 — Local clinical anonymization tool"
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app/     ./app/
COPY static/  ./static/
COPY sample_data/ ./sample_data/
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
