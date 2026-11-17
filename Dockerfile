# The API and the agent worker. The stance reader runs on NumPy: no PyTorch in this image.
FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml ./
COPY src ./src
COPY config ./config
COPY models ./models
RUN pip install --no-cache-dir '.[gcp]' uvicorn
ENV PYTHONUNBUFFERED=1 SCOUT_HOME=/app
USER nobody
CMD ["uvicorn", "--factory", "scout.service.main:create", "--host", "0.0.0.0", "--port", "8080"]
