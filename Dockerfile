FROM mcr.microsoft.com/playwright/python:v1.49.0-jammy
WORKDIR /app
# Primeiro copiamos apenas o requirements para aproveitar o cache do Docker
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN playwright install chromium
# DEPOIS copiamos o resto do código
COPY . .
CMD ["python", "main.py"]
