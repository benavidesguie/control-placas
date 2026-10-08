# Demo de control vehicular por placas (Venezuela)

App que lee placas venezolanas desde fotos, videos o una cámara, las compara
con una lista de placas autorizadas y guarda un registro de accesos.

Motor: FastALPR en modo preciso (detector YOLOv9-s 608 + OCR CCT-s v2) más
reglas de formato venezolano. Corre en un PC normal, sin GPU y sin internet
(solo la primera vez descarga los modelos, unos 35 MB).

## Instalar y abrir

**Windows:** instalar Python 3.10 o más nuevo desde python.org (marcar
"Add Python to PATH"), copiar esta carpeta al PC y hacer doble clic en
`iniciar_windows.bat`. La primera vez instala todo; después abre directo.

**Linux o Mac:**

    python3 -m venv .venv
    .venv/bin/pip install "fast-alpr[onnx]" opencv-python-headless streamlit pandas
    .venv/bin/streamlit run app.py

La app se abre en el navegador en http://localhost:8501

## Uso

- **Leer placas:** elegir Foto, Video o Cámara. Para cámara IP se escribe la
  dirección RTSP (por ejemplo `rtsp://usuario:clave@192.168.1.64:554/Streaming/Channels/101`
  en cámaras Hikvision) o `0` para la cámara USB del PC.
- **Placas autorizadas:** una placa por línea. Las autorizadas salen en verde y
  las demás en rojo.
- **Registro de accesos:** cada carro confirmado queda con fecha, hora, placa,
  estado y una foto. Se puede buscar y descargar en CSV.

Un carro se registra una sola vez aunque aparezca en muchos cuadros: las
lecturas que difieren en una letra se juntan y gana la más repetida.

## Archivos

| Archivo | Qué es |
|---|---|
| `app.py` | La app |
| `motor.py` | Lectura de placas, dibujo y confirmación de carros |
| `reglas_venezuela.py` | Formatos de carro AB123CD, ABC12D y ABC123, y de moto AB1C23D y corrección de letras/números |
| `leer_placas.py` | Versión por línea de comandos |
| `registro.py` | Lista de autorizadas y registro de accesos |
| `vigilar_camara.py` | Servicio que vigila una cámara 24/7 (en el servidor) |
| `datos/` | Se crea al usar la app: autorizadas, `accesos.csv` y fotos (no va en git) |
| `evaluacion/` | Comparación de motores y generadores de placas de prueba |
| `tests/` | Pruebas automáticas |
| `despliegue/` | Instalación en un servidor (Docker, Caddy, `instalar.sh`) |
| `demo/`, `videos/` | Videos de prueba y de referencia (no van en git) |

## Desarrollo

    python3 -m venv .venv
    .venv/bin/pip install -r requirements-dev.txt
    .venv/bin/pytest -m "not modelo"   # pruebas rápidas
    .venv/bin/pytest                   # todas, incluye leer placas con el modelo real

Las pruebas corren solas en GitHub en cada cambio (`.github/workflows/pruebas.yml`).
Para el modo En vivo del servidor con video de demostración, poner un video en
`demo/video_prueba_venezuela.mp4` antes de construir la imagen.

## Límites conocidos

- Probado con placas venezolanas generadas, no con fotos reales todavía.
- De moto solo está el formato vigente (AB1C23D); faltan los antiguos.
- En el formato anterior ABC12D, si la última letra parece un número (Q y 9,
  O y 0) se puede leer como ABC123.
- Para leer bien, la placa debe medir al menos 140 px de ancho en la imagen.
