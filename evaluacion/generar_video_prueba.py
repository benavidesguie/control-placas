"""Crea un video de prueba con placas venezolanas sobre carros reales.

Toma el video 1 (fotos reales de carros), ubica cada placa con el detector y
la reemplaza por una placa venezolana dibujada, siempre la misma para cada
carro. Así el detector ve las placas en su contexto real (sobre un carro).
"""
import os
import random

import cv2
import numpy as np

import sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import motor  # noqa: E402
from generar_sinteticas import dibujar_placa, texto_aleatorio  # noqa: E402

AQUI = os.path.dirname(os.path.abspath(__file__))


def main(desde_s=38, hasta_s=68, salida=os.path.join("..", "demo", "video_prueba_venezuela.mp4")):
    random.seed(3)
    alpr = motor.crear_alpr()
    cap = cv2.VideoCapture(os.path.join(AQUI, "..", "videos", "video1.mp4"))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    cap.set(cv2.CAP_PROP_POS_FRAMES, int(desde_s * fps))
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)); h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    out = cv2.VideoWriter(os.path.join(AQUI, salida), cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))
    def iou(a, b):
        ix = max(0, min(a[2], b[2]) - max(a[0], b[0])); iy = max(0, min(a[3], b[3]) - max(a[1], b[1]))
        inter = ix * iy
        return inter / ((a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter + 1e-9)

    usadas, ultimo, previas = set(), [], []
    i = 0
    while i < (hasta_s - desde_s) * fps:
        ok, frame = cap.read()
        if not ok:
            break
        if i % 3 == 0:  # el detector cada 3 cuadros; entre medio se reutilizan las cajas
            ultimo = []
            for d in alpr.detector.predict(frame):
                b = d.bounding_box
                caja = (b.x1, b.y1, b.x2, b.y2)
                # misma placa si la caja coincide con una de los cuadros anteriores
                previa = max(previas, key=lambda pv: iou(pv[0], caja), default=None)
                if previa and iou(previa[0], caja) > 0.3:
                    texto = previa[1]
                else:
                    texto = texto_aleatorio(random.choices(["vigente", "anterior"], [0.8, 0.2])[0])
                    usadas.add(texto)
                ultimo.append((caja, texto))
            previas = ultimo + [pv for pv in previas if all(iou(pv[0], u[0]) <= 0.3 for u in ultimo)][:20]
        for (x1, y1, x2, y2), texto in ultimo:
            placa = dibujar_placa(texto)
            pw, ph = max(1, x2 - x1), max(1, y2 - y1)
            frame[y1:y1 + ph, x1:x1 + pw] = cv2.resize(placa, (pw, ph), interpolation=cv2.INTER_AREA)[:frame.shape[0] - y1, :frame.shape[1] - x1]
        out.write(frame)
        i += 1
    out.release()
    print("Placas venezolanas puestas:", sorted(usadas))


if __name__ == "__main__":
    main()
