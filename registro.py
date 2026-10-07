"""Lista de placas autorizadas y registro de accesos (archivos en la carpeta datos/).

La carpeta se puede cambiar con la variable de entorno DATOS_DIR (en Docker
apunta a un volumen para que el registro no se pierda al actualizar).
"""
import csv
import json
import os
import time
from datetime import datetime

import cv2

import motor

AQUI = os.path.dirname(os.path.abspath(__file__))
DATOS = os.environ.get("DATOS_DIR", os.path.join(AQUI, "datos"))
CAPTURAS = os.path.join(DATOS, "capturas")
EN_VIVO = os.path.join(DATOS, "en_vivo")
ARCH_AUTORIZADAS = os.path.join(DATOS, "autorizadas.txt")
ARCH_ACCESOS = os.path.join(DATOS, "accesos.csv")
CAMPOS = ["fecha_hora", "placa", "estado", "confianza", "fuente", "captura"]
for d in (CAPTURAS, EN_VIVO):
    os.makedirs(d, exist_ok=True)


def limpiar_placa(texto):
    return texto.strip().upper().replace(" ", "").replace("-", "")


def cargar_autorizadas():
    if not os.path.exists(ARCH_AUTORIZADAS):
        return set()
    with open(ARCH_AUTORIZADAS) as fh:
        return {limpiar_placa(l) for l in fh if l.strip()}


def guardar_autorizadas(placas):
    with open(ARCH_AUTORIZADAS, "w") as fh:
        fh.write("\n".join(sorted(placas)) + ("\n" if placas else ""))


def registrar(f, frame, fuente, cuando=None):
    """Guarda el acceso en accesos.csv y una foto de la placa en capturas/."""
    cuando = cuando or datetime.now()
    autorizadas = cargar_autorizadas()
    nombre = f"{cuando:%Y%m%d_%H%M%S}_{f['placa']}.jpg"
    cv2.imwrite(os.path.join(CAPTURAS, nombre), motor.dibujar(frame, [f], autorizadas))
    nuevo = not os.path.exists(ARCH_ACCESOS)
    fila = {"fecha_hora": f"{cuando:%Y-%m-%d %H:%M:%S}", "placa": f["placa"],
            "estado": motor.estado(f["placa"], autorizadas), "confianza": f"{f['conf_ocr']:.0%}",
            "fuente": fuente, "captura": nombre}
    with open(ARCH_ACCESOS, "a", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=CAMPOS)
        if nuevo:
            w.writeheader()
        w.writerow(fila)
    return fila


def publicar_en_vivo(camara, imagen, info):
    """Deja el último cuadro procesado de una cámara para la pestaña En vivo."""
    tmp = os.path.join(EN_VIVO, f".{camara}.jpg")
    cv2.imwrite(tmp, imagen, [cv2.IMWRITE_JPEG_QUALITY, 75])
    os.replace(tmp, os.path.join(EN_VIVO, f"{camara}.jpg"))
    with open(os.path.join(EN_VIVO, f".{camara}.json"), "w") as fh:
        json.dump({**info, "actualizado": time.time()}, fh)
    os.replace(os.path.join(EN_VIVO, f".{camara}.json"), os.path.join(EN_VIVO, f"{camara}.json"))


def camaras_en_vivo():
    """Cámaras que el servicio de vigilancia está publicando: nombre -> info."""
    out = {}
    for arch in sorted(os.listdir(EN_VIVO)):
        if arch.endswith(".json") and not arch.startswith("."):
            try:
                with open(os.path.join(EN_VIVO, arch)) as fh:
                    out[arch[:-5]] = json.load(fh)
            except (OSError, ValueError):
                pass
    return out
