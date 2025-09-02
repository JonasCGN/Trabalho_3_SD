# Dockerfile para o backend Flask
FROM python:3.11-slim

WORKDIR /app

# Instala dependências do sistema
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    libgtk-3-0 \
    && rm -rf /var/lib/apt/lists/*

# Copia os arquivos do backend
COPY . /app

# Instala dependências Python
RUN pip install -r requirements.txt

EXPOSE 8000

CMD ["python", "app.py"]
