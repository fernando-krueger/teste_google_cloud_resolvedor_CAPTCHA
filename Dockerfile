# Usamos a imagem oficial do Playwright que já tem as dependências do Linux
FROM mcr.microsoft.com/playwright/python:v1.49.0-jammy

# Define o diretório de trabalho
WORKDIR /app

# Copia os arquivos de requisitos e instala as libs
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Instala apenas o navegador Chromium (mais leve que instalar todos)
RUN playwright install chromium

# Copia o restante do código
COPY . .

# Porta padrão do Cloud Run
EXPOSE 8080

# Comando para iniciar o servidor
CMD ["python", "main.py"]