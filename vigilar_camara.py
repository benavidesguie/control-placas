"""Servicio que vigila una cámara todo el tiempo y registra cada carro.

A diferencia del modo Cámara de la app, no depende de tener el navegador
abierto: corre solo, se reconecta si la cámara se cae, y guarda los accesos en
el mismo registro que muestra la app. También publica el último cuadro para la
pestaña "En vivo".

Configuración por variables de entorno:
  CAMARA_URL      rtsp://usuario:clave@IP:554/... , 0 para USB, o un archivo de video
  CAMARA_NOMBRE   nombre corto que sale en el registro (por defecto "entrada")
  CUADROS_SEG     cuántos cuadros por segundo analizar (por defecto 4)
  ESPERA_SEG      segundos antes de volver a registrar la misma placa (por defecto 60)
  SOLO_VENEZUELA  1 para aplicar el formato venezolano (por defecto), 0 para no
  REPETIR_VIDEO   1 para repetir un archivo de video en bucle (para demos)
"""
import os
import time

import cv2

import motor
import registro

URL = os.environ.get("CAMARA_URL", "")
NOMBRE = os.environ.get("CAMARA_NOMBRE", "entrada")
CUADROS_SEG = float(os.environ.get("CUADROS_SEG", "4"))
ESPERA = float(os.environ.get("ESPERA_SEG", "60"))
REGLAS = os.environ.get("SOLO_VENEZUELA", "1") == "1"
REPETIR = os.environ.get("REPETIR_VIDEO", "0") == "1"


def log(msg):
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {NOMBRE}: {msg}", flush=True)


def abrir():
    fuente = int(URL) if URL.isdigit() else URL
    if isinstance(fuente, str) and fuente.startswith("rtsp"):
        os.environ.setdefault("OPENCV_FFMPEG_CAPTURE_OPTIONS", "rtsp_transport;tcp")
    return cv2.VideoCapture(fuente)


def main():
    if not URL or (URL.startswith("/") and not os.path.exists(URL)):
        log(f"Falta CAMARA_URL o no existe '{URL}'. No hay nada que vigilar.")
        while True:
            time.sleep(3600)
    alpr = motor.crear_alpr()
    conf = motor.Confirmador(espera_s=ESPERA)
    es_archivo = os.path.isfile(URL)
    intervalo = 1.0 / CUADROS_SEG
    espera_reconexion = 2
    while True:
        cap = abrir()
        if not cap.isOpened():
            log(f"No se pudo abrir la cámara. Reintento en {espera_reconexion} s.")
            time.sleep(espera_reconexion)
            espera_reconexion = min(espera_reconexion * 2, 60)
            continue
        log("Cámara conectada.")
        espera_reconexion = 2
        fps_video = cap.get(cv2.CAP_PROP_FPS) or 25
        saltar = max(1, round(fps_video / CUADROS_SEG)) if es_archivo else 1
        fallos, ultimo, i = 0, 0.0, 0
        while True:
            if es_archivo:
                # Un archivo se lee al ritmo real del video, como si fuera una cámara
                ok, frame = cap.read()
                i += 1
                if ok and i % saltar:
                    continue
                time.sleep(max(0.0, intervalo - (time.time() - ultimo)))
            else:
                ok = cap.grab()  # descarta cuadros viejos para analizar siempre el más reciente
                if ok and time.time() - ultimo < intervalo:
                    continue
                ok, frame = cap.retrieve() if ok else (False, None)
            if not ok:
                fallos += 1
                if es_archivo or fallos > 25:
                    break
                time.sleep(0.05)
                continue
            fallos, ultimo = 0, time.time()
            t0 = time.time()
            lecturas = motor.leer(alpr, frame, REGLAS)
            for f in lecturas:
                f["cuadro"] = frame
            for f in conf.agregar(lecturas):
                fila = registro.registrar(f, f["cuadro"], NOMBRE)
                log(f"{fila['placa']} {fila['estado']} ({fila['confianza']})")
            vista = motor.dibujar(frame, lecturas, registro.cargar_autorizadas())
            alto = 540
            vista = cv2.resize(vista, (int(vista.shape[1] * alto / vista.shape[0]), alto))
            registro.publicar_en_vivo(NOMBRE, vista, {"ms_lectura": round((time.time() - t0) * 1000)})
        cap.release()
        for f in conf.terminar():
            registro.registrar(f, f["cuadro"], NOMBRE)
        if es_archivo and REPETIR:
            continue
        if es_archivo:
            log("Fin del video.")
            while True:
                time.sleep(3600)
        log("Se perdió la señal. Reconectando...")


if __name__ == "__main__":
    main()
