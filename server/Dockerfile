FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN mkdir -p /app/partage /app/jsonAPI
COPY . .
CMD ["python", "main.py"]
EXPOSE 80
#HEALTHCHECK --interval=30s --timeout=5s CMD curl -f http://localhost/health || exit 1