# Build context is the REPO ROOT (see compose) so the image can copy the shared adapters/ package.
FROM python:3.12-slim
WORKDIR /app
COPY stack/api/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY adapters/ ./adapters/
COPY ferc/ ./ferc/
COPY projects/ ./projects/
COPY stack/api/ ./
EXPOSE 8000
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
