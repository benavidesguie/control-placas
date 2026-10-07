"""Demo de lectura de placas venezolanas (ALPR) con FastALPR.

Usa la opción que ganó en evaluacion/: detector YOLOv9-s 608 + OCR CCT-s v2,
más las reglas de formato venezolano (reglas_venezuela.py), que corrigen
confusiones como O/0 o B/8 y descartan lo que no es una placa venezolana.

Uso:
  python3 leer_placas.py imagen.jpg [otra.jpg ...]   -> guarda *_resultado.jpg
  python3 leer_placas.py video.mp4 --cada 15          -> analiza 1 de cada N cuadros
  --sin-reglas  lee cualquier placa (por ejemplo, las de los videos de referencia)
"""
import argparse
import collections
import csv
import os
import sys

import cv2

import motor

VIDEO_EXT = {".mp4", ".avi", ".mov", ".mkv"}
USAR_REGLAS = True


def leer(alpr, frame):
    return motor.leer(alpr, frame, USAR_REGLAS)


def procesar_imagen(alpr, ruta, salida):
    frame = cv2.imread(ruta)
    filas = leer(alpr, frame)
    dibujada = motor.dibujar(frame, filas)
    base = os.path.splitext(os.path.basename(ruta))[0]
    cv2.imwrite(os.path.join(salida, f"{base}_resultado.jpg"), dibujada)
    return [{"origen": os.path.basename(ruta), **f} for f in filas]


def procesar_video(alpr, ruta, salida, cada):
    cap = cv2.VideoCapture(ruta)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    filas, i = [], 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        if i % cada == 0:
            encontradas = leer(alpr, frame)
            if encontradas:
                dib = motor.dibujar(frame, encontradas)
                cv2.imwrite(os.path.join(salida, f"cuadro_{i:05d}.jpg"), dib)
            for f in encontradas:
                filas.append({"origen": f"{os.path.basename(ruta)}@{i / fps:.1f}s", **f})
        i += 1
    return filas


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("entradas", nargs="+")
    ap.add_argument("--salida", default="resultados")
    ap.add_argument("--cada", type=int, default=15, help="en video: analizar 1 de cada N cuadros")
    ap.add_argument("--min-conf", type=float, default=0.9, help="confianza OCR mínima para el resumen")
    ap.add_argument("--sin-reglas", action="store_true", help="no aplicar el formato venezolano")
    a = ap.parse_args()
    global USAR_REGLAS
    USAR_REGLAS = not a.sin_reglas
    os.makedirs(a.salida, exist_ok=True)
    alpr = motor.crear_alpr()
    filas = []
    for e in a.entradas:
        if os.path.splitext(e)[1].lower() in VIDEO_EXT:
            filas += procesar_video(alpr, e, a.salida, a.cada)
        else:
            filas += procesar_imagen(alpr, e, a.salida)
    for f in filas:
        print(f"{f['origen']:<28} {f['placa']:<12} det={f['conf_deteccion']:.2f} ocr={f['conf_ocr']:.2f}")
    if filas:
        with open(os.path.join(a.salida, "placas.csv"), "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(filas[0].keys()))
            w.writeheader()
            w.writerows(filas)
    # Resumen: placas distintas, contando solo lecturas con OCR confiable
    conteo = collections.Counter(f["placa"] for f in filas if f["conf_ocr"] >= a.min_conf)
    print("\nPlacas detectadas (veces vistas):")
    for placa, n in conteo.most_common():
        print(f"  {placa:<12} {n}")
    print(f"\n{len(filas)} lecturas. Resultados en {a.salida}/", file=sys.stderr)


if __name__ == "__main__":
    main()
