FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 DATOS_DIR=/datos
WORKDIR /app

RUN pip install "fast-alpr[onnx]" opencv-python-headless streamlit pandas

COPY motor.py reglas_venezuela.py registro.py app.py vigilar_camara.py leer_placas.py ./
COPY .streamlit .streamlit
COPY demo demo

# Descarga los modelos al construir, para que el servidor no dependa de internet al arrancar
RUN DATOS_DIR=/tmp/datos python -c "import motor; motor.crear_alpr()"

EXPOSE 8501
CMD ["streamlit", "run", "app.py", "--server.address=0.0.0.0", "--server.port=8501", "--server.headless=true"]
