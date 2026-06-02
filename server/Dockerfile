FROM python:3.11-slim
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

RUN mkdir -p /app/ics /app/jsonAPI /app/partage
COPY cesi-fr-chain.pem /app/cesi-fr-chain.pem
COPY main.py scrap.py convertissor.py ./

CMD ["python", "main.py"]
