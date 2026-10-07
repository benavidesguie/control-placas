"""Compara varias opciones de lectura de placas con las mismas imágenes.

Opciones (todas corren local, en CPU, gratis):
  A  FastALPR rápido   detector YOLOv9-t 384 + OCR CCT-xs v1 (lo del video 1)
  B  FastALPR preciso  detector YOLOv9-s 608 + OCR CCT-s v2
  C  Detector + EasyOCR  detector YOLOv9-s 608 + OCR genérico EasyOCR
Cada opción se mide sin y con las reglas de formato venezolano.

Pruebas:
  sinteticas  80 fotos de placas venezolanas dibujadas (texto real conocido);
              se mide solo el OCR sobre el recorte de la placa
  video1      tutorial FastALPR, 6 placas conocidas
  video2      cámaras de tablero (placas colombianas), 2 placas legibles a ojo
              (en video2 se corta cada cámara y se amplía 2x antes de leer)
  En los videos las placas no son venezolanas, así que ahí solo cuenta la
  lectura sin reglas.

Uso: python3 evaluar_opciones.py   -> resultados_comparacion/
"""
import collections
import csv
import json
import os
import re
import time

import cv2
import numpy as np
from fast_alpr import ALPR
from fast_alpr.default_detector import DefaultDetector
from fast_alpr.default_ocr import DefaultOCR

import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from reglas_venezuela import normalizar  # noqa: E402

AQUI = os.path.dirname(os.path.abspath(__file__))
VIDEOS = os.path.join(AQUI, "..", "videos")  # video1.mp4 y video2.mp4 de referencia (no van en el repositorio)
SALIDA = os.path.join(AQUI, "resultados_comparacion")

GT_VIDEO1 = {"LM1AB2X", "5AU5341", "QNA4B79", "127RFS", "YK65XHP", "6GQW015"}
GT_VIDEO2 = {"JIO939", "KYX537"}
FRANJAS_VIDEO2 = [(0, 400), (427, 827), (853, 1253)]  # las tres cámaras apiladas


def limpiar(t):
    return re.sub(r"[^A-Z0-9]", "", (t or "").upper())


class Motor:
    """Detector de placas (YOLOv9 de FastALPR) + un OCR intercambiable."""

    def __init__(self, detector):
        self.det = DefaultDetector(model_name=detector, conf_thresh=0.3)

    def leer(self, img):
        out = []
        for d in self.det.predict(img):
            b = d.bounding_box
            recorte = img[max(0, b.y1):min(b.y2, img.shape[0]), max(0, b.x1):min(b.x2, img.shape[1])]
            if recorte.size:
                r = self.leer_recorte(recorte)
                if r:
                    out.append(r)
        return out


class MotorFastALPR(Motor):
    def __init__(self, detector, ocr):
        super().__init__(detector)
        self.ocr = DefaultOCR(hub_ocr_model=ocr)

    def leer_recorte(self, recorte):
        r = self.ocr.predict(recorte)
        if r and r.text:
            c = float(np.mean(r.confidence)) if isinstance(r.confidence, list) else float(r.confidence)
            return limpiar(r.text), c


class MotorEasyOCR(Motor):
    def __init__(self, detector):
        import easyocr
        super().__init__(detector)
        self.ocr = easyocr.Reader(["en"], gpu=False, verbose=False)

    def leer_recorte(self, recorte):
        recorte = cv2.resize(recorte, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
        res = self.ocr.readtext(recorte, allowlist="ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789")
        # Ordena por renglón (las motos traen 2 líneas) y descarta textos pequeños (ciudad)
        res = sorted(res, key=lambda r: (round(np.mean([p[1] for p in r[0]]) / 20), r[0][0][0]))
        alto = max((r[0][2][1] - r[0][0][1] for r in res), default=0)
        partes = [(limpiar(t), c) for q, t, c in res if (q[2][1] - q[0][1]) > 0.5 * alto and limpiar(t)]
        if partes:
            return "".join(p for p, _ in partes), float(np.mean([c for _, c in partes]))


MOTORES = {
    "A  FastALPR rápido": lambda: MotorFastALPR("yolo-v9-t-384-license-plate-end2end", "cct-xs-v1-global-model"),
    "B  FastALPR preciso": lambda: MotorFastALPR("yolo-v9-s-608-license-plate-end2end", "cct-s-v2-global-model"),
    "D  FastALPR OCR MobileViT": lambda: MotorFastALPR("yolo-v9-s-608-license-plate-end2end", "global-plates-mobile-vit-v2-model"),
    "C  Detector + EasyOCR": lambda: MotorEasyOCR("yolo-v9-s-608-license-plate-end2end"),
}


def mejor(lecturas, reglas):
    cands = []
    for t, c in lecturas:
        if reglas:
            t = normalizar(t)
        if t:
            cands.append((t, c))
    return max(cands, key=lambda x: x[1])[0] if cands else None


def prueba_sinteticas(motor):
    carpeta = os.path.join(AQUI, "sinteticas")
    filas = list(csv.DictReader(open(os.path.join(carpeta, "etiquetas.csv"))))
    res = {False: [], True: []}
    t0 = time.time()
    for f in filas:
        img = cv2.imread(os.path.join(carpeta, f["imagen"]))
        # El detector no reconoce bien placas pegadas fuera de un carro, así que
        # aquí se mide el OCR sobre el recorte real de la placa (con margen).
        x1, y1, x2, y2 = (int(f[k]) for k in ("x1", "y1", "x2", "y2"))
        m = int(0.06 * (x2 - x1))
        recorte = img[max(0, y1 - m):y2 + m, max(0, x1 - m):x2 + m]
        r = motor.leer_recorte(recorte)
        lect = [r] if r else []
        for reglas in (False, True):
            res[reglas].append({**f, "leido": mejor(lect, reglas) or ""})
    ms = (time.time() - t0) / len(filas) * 1000
    return res, ms


def cuadros_video(nombre, cada, hasta_s=None, franjas=None):
    cap = cv2.VideoCapture(os.path.join(VIDEOS, nombre))
    i = 0
    while True:
        ok, f = cap.read()
        if not ok or (hasta_s and i > hasta_s * 30):
            break
        if i % cada == 0:
            if franjas:
                for y0, y1 in franjas:
                    yield cv2.resize(f[y0:y1], None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
            else:
                yield f
        i += 1


def prueba_video(motor, nombre, gt, cada, hasta_s=None, franjas=None):
    """Lee el video y agrupa por placa: 'confirmada' = vista 2+ veces o una vez con confianza >= 0.85."""
    if not os.path.exists(os.path.join(VIDEOS, nombre)):
        print(f"  (no está {nombre}; se omite esa prueba)")
        vacio = {"encontradas": [], "falsas": [], "lecturas_totales": 0, "lecturas_correctas": 0}
        return {False: vacio, True: vacio}, 0
    votos = {False: collections.Counter(), True: collections.Counter()}
    maxc = {False: collections.defaultdict(float), True: collections.defaultdict(float)}
    n, t0 = 0, time.time()
    for img in cuadros_video(nombre, cada, hasta_s, franjas):
        lect = motor.leer(img)
        n += 1
        for reglas in (False, True):
            for t, c in lect:
                t2 = normalizar(t) if reglas else t
                if t2 and c >= 0.5:
                    votos[reglas][t2] += 1
                    maxc[reglas][t2] = max(maxc[reglas][t2], c)
    ms = (time.time() - t0) / max(n, 1) * 1000
    out = {}
    for reglas, v in votos.items():
        confirmadas = {p for p, k in v.items() if k >= 2 or maxc[reglas][p] >= 0.85}
        out[reglas] = {
            "encontradas": sorted(confirmadas & gt),
            "falsas": sorted(confirmadas - gt),
            "lecturas_totales": sum(v.values()),
            "lecturas_correctas": sum(k for p, k in v.items() if p in gt),
        }
    return out, ms


def main():
    os.makedirs(SALIDA, exist_ok=True)
    resumen = {}
    detalle_sint = []
    for nombre, crear in MOTORES.items():
        print(f"== {nombre}")
        motor = crear()
        sint, ms_s = prueba_sinteticas(motor)
        v1, ms_1 = prueba_video(motor, "video1.mp4", GT_VIDEO1, cada=15)
        v2, ms_2 = prueba_video(motor, "video2.mp4", GT_VIDEO2, cada=5, hasta_s=11, franjas=FRANJAS_VIDEO2)
        for reglas in (False, True):
            filas = sint[reglas]
            ok = [f for f in filas if f["leido"] == f["placa"]]
            por_ancho = {}
            for a in sorted({int(f["ancho_px"]) for f in filas}):
                sub = [f for f in filas if int(f["ancho_px"]) == a]
                por_ancho[a] = round(100 * sum(f["leido"] == f["placa"] for f in sub) / len(sub))
            vig = [f for f in filas if f["formato"] == "vigente"]
            clave = nombre + (" + reglas VE" if reglas else "")
            resumen[clave] = {
                "sint_acierto_pct": round(100 * len(ok) / len(filas)),
                "sint_por_ancho_px": por_ancho,
                "sint_formato_vigente_pct": round(100 * sum(f["leido"] == f["placa"] for f in vig) / len(vig)),
                "sint_lecturas_erradas": sum(1 for f in filas if f["leido"] and f["leido"] != f["placa"]),
                "video1": v1[reglas],
                "video2": v2[reglas],
                "ms_por_imagen_sint": round(ms_s),
                "ms_por_cuadro_video1": round(ms_1),
            }
            for f in filas:
                detalle_sint.append({"opcion": clave, **f})
            r = resumen[clave]
            print(f"  {clave:<38} sint={r['sint_acierto_pct']}% erradas={r['sint_lecturas_erradas']} "
                  f"v1={len(r['video1']['encontradas'])}/6 falsas={len(r['video1']['falsas'])} "
                  f"v2={len(r['video2']['encontradas'])}/2 falsas={len(r['video2']['falsas'])} {r['ms_por_imagen_sint']}ms")
    json.dump(resumen, open(os.path.join(SALIDA, "resumen.json"), "w"), indent=2, ensure_ascii=False)
    with open(os.path.join(SALIDA, "detalle_sinteticas.csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(detalle_sint[0].keys()))
        w.writeheader()
        w.writerows(detalle_sint)
    print(f"\nResultados en {SALIDA}/")


if __name__ == "__main__":
    main()
