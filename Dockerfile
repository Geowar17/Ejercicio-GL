# Usa una imagen base oficial de Python
FROM python:3.11-slim

# Establece el directorio de trabajo dentro del contenedor
WORKDIR /usr/src/app

# Copia los archivos de requerimientos e instala las dependencias
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copia el resto de tu código de la aplicación
COPY . .

# Expone el puerto en el que se ejecutará la API (por ejemplo, 3000)
EXPOSE 3000

# Define el comando para ejecutar la aplicación
CMD ["python", "app.py"]