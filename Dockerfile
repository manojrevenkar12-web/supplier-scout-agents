FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml ./
COPY src ./src
COPY config ./config
RUN pip install --no-cache-dir '.[gcp]' uvicorn
ENV PYTHONUNBUFFERED=1
CMD ["uvicorn", "scout.service.main:app", "--host", "0.0.0.0", "--port", "8080"]
