# Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Copy dan install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Masukkan seluruh kode
COPY . .

# Port Railway ada di $PORT
ENV PORT=${PORT}

# Jalankan Flask
CMD ["sh","-c","flask run --host=0.0.0.0 --port=$PORT --app app"]
