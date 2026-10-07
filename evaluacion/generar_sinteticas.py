"""Genera fotos sintéticas de placas venezolanas para probar el OCR.

No hay fotos reales de placas venezolanas disponibles aquí, así que se dibujan
placas blancas con "VENEZUELA" arriba, el estado abajo y los formatos de carro
(vigente AB123CD, anteriores ABC12D y ABC123), y se pegan sobre
fondos de calle tomados del video 2, con perspectiva, desenfoque, ruido y
compresión JPEG variables. Cada imagen trae su texto real en etiquetas.csv.
"""
import csv
import os
import random
import string

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

FUENTE = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
ESTADOS = ["DISTRITO CAPITAL", "MIRANDA", "ZULIA", "CARABOBO", "LARA", "ARAGUA", "ANZOATEGUI", "BOLIVAR"]
BLANCO = (245, 245, 245)


def texto_aleatorio(formato):
    L = lambda k: "".join(random.choices(string.ascii_uppercase, k=k))
    N = lambda k: "".join(random.choices(string.digits, k=k))
    if formato == "vigente":
        return L(2) + N(3) + L(2)
    if formato == "anterior":
        return L(3) + N(2) + L(1)
    return L(3) + N(3)


def fuente_que_cabe(d, texto, ancho_max, alto_max):
    t = 120
    while t > 10:
        f = ImageFont.truetype(FUENTE, t)
        x0, y0, x1, y1 = d.textbbox((0, 0), texto, font=f)
        if x1 - x0 <= ancho_max and y1 - y0 <= alto_max:
            return f
        t -= 2
    return ImageFont.truetype(FUENTE, t)


def dibujar_placa(texto):
    w, h = 330, 160
    img = Image.new("RGB", (w, h), BLANCO)
    d = ImageDraw.Draw(img)
    d.rectangle([3, 3, w - 4, h - 4], outline=(20, 20, 20), width=4)
    # Franja tricolor y "VENEZUELA" arriba, estado abajo
    for k, color in enumerate([(252, 209, 22), (0, 56, 147), (207, 20, 43)]):
        d.rectangle([8, 9 + 4 * k, w - 9, 12 + 4 * k], fill=color)
    d.text((w / 2, 34), "VENEZUELA", font=ImageFont.truetype(FUENTE, 18), fill=(0, 56, 147), anchor="mm")
    f = fuente_que_cabe(d, texto, w * 0.9, 80)
    d.text((w / 2, 88), texto, font=f, fill=(15, 15, 15), anchor="mm")
    d.text((w / 2, 140), random.choice(ESTADOS), font=ImageFont.truetype(FUENTE, 16), fill=(15, 15, 15), anchor="mm")
    return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)


def fondos(video, n=40):
    """Fondos de calle tomados del video; si no está, fondos grises con textura."""
    if not os.path.exists(video):
        out = []
        for _ in range(n):
            base = np.full((720, 1280, 3), random.randint(60, 190), np.uint8)
            out.append(cv2.GaussianBlur(np.clip(base + np.random.normal(0, 25, base.shape), 0, 255).astype(np.uint8), (0, 0), 3))
        return out
    cap = cv2.VideoCapture(video)
    out = []
    for i in range(0, 315, 8):
        cap.set(cv2.CAP_PROP_POS_FRAMES, i)
        ok, f = cap.read()
        if ok:
            out.append(cv2.resize(f[0:400], (1280, 720)))
    random.shuffle(out)
    return out[:n]


def pegar(fondo, placa, ancho_px):
    h, w = placa.shape[:2]
    escala = ancho_px / w
    pw, ph = int(w * escala), int(h * escala)
    x = random.randint(50, fondo.shape[1] - pw - 50)
    y = random.randint(300, fondo.shape[0] - ph - 30)
    j = 0.08 * pw  # inclinación / perspectiva
    src = np.float32([[0, 0], [w, 0], [w, h], [0, h]])
    dst = np.float32([[x + random.uniform(-j, j), y + random.uniform(-j, j) * 0.5],
                      [x + pw + random.uniform(-j, j), y + random.uniform(-j, j) * 0.5],
                      [x + pw + random.uniform(-j, j), y + ph + random.uniform(-j, j) * 0.5],
                      [x + random.uniform(-j, j), y + ph + random.uniform(-j, j) * 0.5]])
    M = cv2.getPerspectiveTransform(src, dst)
    warped = cv2.warpPerspective(placa, M, (fondo.shape[1], fondo.shape[0]))
    mask = cv2.warpPerspective(np.full((h, w), 255, np.uint8), M, (fondo.shape[1], fondo.shape[0]))
    out = fondo.copy()
    out[mask > 0] = warped[mask > 0]
    x1, y1 = dst.min(axis=0)
    x2, y2 = dst.max(axis=0)
    return out, (int(x1), int(y1), int(x2), int(y2))


def main(salida="sinteticas", n=80, semilla=7):
    random.seed(semilla)
    np.random.seed(semilla)
    os.makedirs(salida, exist_ok=True)
    fs = fondos(os.path.join(os.path.dirname(__file__), "..", "video2.mp4"))
    filas = []
    for i in range(n):
        formato = random.choices(["vigente", "anterior", "antiguo"], [0.7, 0.2, 0.1])[0]
        texto = texto_aleatorio(formato)
        # Dificultad: ancho de la placa en píxeles y desenfoque
        ancho = random.choice([70, 100, 140, 200])
        img, caja = pegar(fs[i % len(fs)], dibujar_placa(texto), ancho)
        blur = random.choice([0, 0, 3, 5])
        if blur:
            img = cv2.GaussianBlur(img, (blur, blur), 0)
        img = np.clip(img + np.random.normal(0, random.choice([2, 6, 10]), img.shape), 0, 255).astype(np.uint8)
        nombre = f"sint_{i:03d}.jpg"
        cv2.imwrite(os.path.join(salida, nombre), img, [cv2.IMWRITE_JPEG_QUALITY, random.choice([50, 70, 90])])
        filas.append({"imagen": nombre, "placa": texto, "formato": formato,
                      "ancho_px": ancho, "desenfoque": blur,
                      "x1": caja[0], "y1": caja[1], "x2": caja[2], "y2": caja[3]})
    with open(os.path.join(salida, "etiquetas.csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(filas[0].keys()))
        w.writeheader()
        w.writerows(filas)
    print(f"{n} imágenes en {salida}/")


if __name__ == "__main__":
    main()
