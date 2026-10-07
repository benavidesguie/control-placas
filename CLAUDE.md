# Control vehicular por placas (Venezuela)

- Idioma del proyecto: español (código, comentarios, textos de la app y mensajes de commit).
- Motor elegido: FastALPR "preciso" (yolo-v9-s-608 + cct-s-v2-global) en `motor.py`; no cambiarlo sin una comparación en `evaluacion/`.
- Las placas son venezolanas: `reglas_venezuela.py` (AB123CD, ABC12D, ABC123). Las motos aún no están.
- Antes de subir cambios: `pytest -m "not modelo"`; si tocas `motor.py` o las reglas, también `pytest -m modelo`.
- No subir videos, `datos/`, `.env` ni `despliegue/Caddyfile` (tiene la contraseña).
