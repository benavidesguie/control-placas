"""Motor de lectura de placas: FastALPR preciso + reglas de formato venezolano.

Lo usan la app (app.py) y la línea de comandos (leer_placas.py).
"""
import time

import cv2
from fast_alpr import ALPR

from reglas_venezuela import normalizar

VERDE = (60, 170, 60)
ROJO = (40, 40, 220)
GRIS = (150, 150, 150)


def crear_alpr():
    return ALPR(
        detector_model="yolo-v9-s-608-license-plate-end2end",
        ocr_model="cct-s-v2-global-model",
        detector_conf_thresh=0.3,
    )


def leer(alpr, frame, reglas=True):
    """Lista de lecturas: placa, confianzas y caja (x1, y1, x2, y2)."""
    filas = []
    for r in alpr.predict(frame):
        if r.ocr is None or not r.ocr.text:
            continue
        placa = normalizar(r.ocr.text) if reglas else r.ocr.text
        if not placa:
            continue
        conf_ocr = r.ocr.confidence
        if isinstance(conf_ocr, list):
            conf_ocr = sum(conf_ocr) / len(conf_ocr)
        b = r.detection.bounding_box
        filas.append({
            "placa": placa,
            "conf_deteccion": round(float(r.detection.confidence), 3),
            "conf_ocr": round(float(conf_ocr), 3),
            "caja": (b.x1, b.y1, b.x2, b.y2),
        })
    return filas


def estado(placa, autorizadas):
    if not autorizadas:
        return "Leída"
    return "Autorizada" if placa in autorizadas else "No registrada"


def dibujar(frame, lecturas, autorizadas=None):
    """Marca cada placa: verde si está autorizada, rojo si no, gris sin lista."""
    img = frame.copy()
    grosor = max(2, img.shape[1] // 500)
    escala = max(0.6, img.shape[1] / 1400)
    for f in lecturas:
        e = estado(f["placa"], autorizadas)
        color = VERDE if e == "Autorizada" else ROJO if e == "No registrada" else GRIS
        x1, y1, x2, y2 = f["caja"]
        cv2.rectangle(img, (x1, y1), (x2, y2), color, grosor)
        texto = f"{f['placa']} {f['conf_ocr']:.0%}"
        (tw, th), _ = cv2.getTextSize(texto, cv2.FONT_HERSHEY_SIMPLEX, escala, grosor)
        y_txt = max(th + 6, y1 - 6)
        cv2.rectangle(img, (x1, y_txt - th - 6), (x1 + tw + 8, y_txt + 4), color, -1)
        cv2.putText(img, texto, (x1 + 4, y_txt), cv2.FONT_HERSHEY_SIMPLEX, escala, (255, 255, 255), grosor)
    return img


def distancia(a, b):
    """Cuántos caracteres hay que cambiar, quitar o poner para pasar de a a b."""
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


class Confirmador:
    """Convierte lecturas sueltas en eventos de acceso, uno por carro.

    Las lecturas que difieren en un solo carácter y llegan seguidas se juntan
    como el mismo carro (el OCR a veces confunde una letra en algunos cuadros).
    Cuando el carro deja de verse por `cierre_s` segundos se decide su placa
    por mayoría de votos. Se reporta si tuvo 2+ lecturas, o una sola con
    confianza >= `conf_alta`. La misma placa no se vuelve a reportar hasta
    pasados `espera_s` segundos.
    """

    def __init__(self, cierre_s=1.5, conf_alta=0.85, espera_s=60, conf_min=0.5):
        self.cierre_s, self.conf_alta, self.espera_s, self.conf_min = cierre_s, conf_alta, espera_s, conf_min
        self.grupos = []       # carros a la vista: votos, confianza, mejor lectura
        self.reportada = {}    # placa -> último tiempo reportado

    def agregar(self, lecturas, t=None):
        """Agrega las lecturas de un cuadro; devuelve los carros que se acaban de confirmar."""
        t = time.time() if t is None else t
        for f in lecturas:
            if f["conf_ocr"] < self.conf_min:
                continue
            g = next((g for g in self.grupos if distancia(g["lider"], f["placa"]) <= 1), None)
            if g is None:
                g = {"votos": {}, "confs": {}, "mejor": {}, "lider": f["placa"]}
                self.grupos.append(g)
            p = f["placa"]
            g["votos"][p] = g["votos"].get(p, 0) + 1
            g["confs"][p] = max(g["confs"].get(p, 0), f["conf_ocr"])
            if f["conf_ocr"] >= g["mejor"].get(p, {}).get("conf_ocr", -1):
                g["mejor"][p] = f
            g["lider"] = max(g["votos"], key=lambda k: (g["votos"][k], g["confs"][k]))
            g["t"] = t
        return self._cerrar(lambda g: t - g["t"] > self.cierre_s, t)

    def terminar(self, t=None):
        """Cierra los carros que siguen a la vista (al final de un video)."""
        return self._cerrar(lambda g: True, time.time() if t is None else t)

    def _cerrar(self, condicion, t):
        nuevas, quedan = [], []
        for g in self.grupos:
            if not condicion(g):
                quedan.append(g)
                continue
            p = g["lider"]
            total = sum(g["votos"].values())
            if (total >= 2 or g["confs"][p] >= self.conf_alta) and t - self.reportada.get(p, -1e9) >= self.espera_s:
                self.reportada[p] = t
                nuevas.append({**g["mejor"][p], "lecturas": total})
        self.grupos = quedan
        return nuevas
