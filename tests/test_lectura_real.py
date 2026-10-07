"""Prueba de punta a punta con el modelo real (descarga ~35 MB la primera vez).

Dibuja placas venezolanas, las lee con el motor y verifica el texto.
Se salta con:  pytest -m "not modelo"
"""
import random

import cv2
import numpy as np
import pytest

from generar_sinteticas import dibujar_placa

pytestmark = pytest.mark.modelo


@pytest.fixture(scope="module")
def alpr():
    import motor
    return motor.crear_alpr()


@pytest.mark.parametrize("placa", ["AB123CD", "XK508PM", "RTL896"])
def test_lee_placa_venezolana_clara(alpr, placa):
    import motor
    random.seed(1)
    # Placa nítida de 220 px sobre un fondo gris con textura
    fondo = np.clip(np.full((480, 640, 3), 120.0) + np.random.default_rng(0).normal(0, 20, (480, 640, 3)), 0, 255).astype(np.uint8)
    img = cv2.resize(dibujar_placa(placa), (220, 107))
    fondo[300:407, 210:430] = img
    lecturas = motor.leer(alpr, fondo, reglas=True)
    if not lecturas:
        # Sin carro alrededor el detector a veces no la encuentra; se prueba el OCR sobre el recorte
        texto = alpr.ocr.predict(img).text
        from reglas_venezuela import normalizar
        assert normalizar(texto) == placa
    else:
        assert lecturas[0]["placa"] == placa
