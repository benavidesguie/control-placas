"""App de demo: control de acceso vehicular por lectura de placas venezolanas.

Ejecutar:  streamlit run app.py
Luego abrir http://localhost:8501 en el navegador.
"""
import os
import tempfile
import time
from datetime import datetime

import cv2
import numpy as np
import pandas as pd
import streamlit as st

import motor
import registro
from registro import cargar_autorizadas, registrar
from reglas_venezuela import tipo_vehiculo

st.set_page_config(page_title="Control vehicular", page_icon="🚗", layout="wide")


@st.cache_resource(show_spinner="Cargando modelos de lectura de placas...")
def alpr():
    return motor.crear_alpr()


def evento_video(f, nombre, guardar, autorizadas):
    if guardar:
        return registrar(f, f["cuadro"], f"video {nombre} @ {f['t']:.1f}s")
    return {"fecha_hora": f"{f['t']:.1f} s", "placa": f["placa"],
            "estado": motor.estado(f["placa"], autorizadas), "confianza": f"{f['conf_ocr']:.0%}"}


def a_rgb(img):
    return cv2.cvtColor(img, cv2.COLOR_BGR2RGB)


def tabla_eventos(eventos):
    if eventos:
        df = pd.DataFrame(eventos)
        df["tipo"] = df["placa"].map(tipo_vehiculo)
        st.dataframe(df[["fecha_hora", "placa", "tipo", "estado", "confianza"]],
                     hide_index=True, width="stretch")
    else:
        st.caption("Todavía no se ha confirmado ninguna placa.")


# ---------------------------------------------------------------- barra lateral
with st.sidebar:
    st.header("Ajustes")
    reglas = st.toggle("Solo placas venezolanas", value=True,
                       help="Corrige confusiones como O/0 o B/8 y descarta textos que no son placas "
                            "venezolanas (AB123CD, ABC12D, ABC123). Apágalo para probar con placas de otros países.")
    cada = st.slider("En video, analizar 1 de cada N cuadros", 1, 30, 5,
                     help="Más alto = más rápido, pero puede perder carros que pasan rápido.")
    espera = st.slider("No repetir la misma placa durante (segundos)", 10, 600, 60)
    st.divider()
    st.caption("Motor: FastALPR preciso (YOLOv9-s 608 + OCR CCT-s v2), en CPU.")

st.title("Control vehicular por placas")
tab_vivo, tab_leer, tab_registro, tab_autorizadas = st.tabs(
    ["En vivo", "Leer placas", "Registro de accesos", "Placas autorizadas"])


def leer_accesos():
    if os.path.exists(registro.ARCH_ACCESOS):
        df = pd.read_csv(registro.ARCH_ACCESOS)
        # El tipo se deduce de la placa, así los registros viejos también lo tienen
        df.insert(2, "tipo", df["placa"].map(tipo_vehiculo))
        return df
    return None


# ---------------------------------------------------------------- en vivo
@st.fragment(run_every=2)
def en_vivo():
    camaras = registro.camaras_en_vivo()
    if not camaras:
        st.info("No hay cámaras conectadas al servicio de vigilancia. En el servidor se configura con "
                "CAMARA_URL (ver LEEME.md). Mientras tanto puedes usar la pestaña Leer placas.")
        return
    c1, c2 = st.columns([3, 2])
    with c1:
        for nombre, info in camaras.items():
            hace = time.time() - info.get("actualizado", 0)
            estado = "🟢 conectada" if hace < 15 else f"🔴 sin señal hace {hace / 60:.0f} min"
            st.markdown(f"**{nombre}** · {estado} · lectura {info.get('ms_lectura', 0)} ms")
            ruta = os.path.join(registro.EN_VIVO, f"{nombre}.jpg")
            if os.path.exists(ruta):
                st.image(ruta, width="stretch")
    with c2:
        st.subheader("Últimos accesos")
        df = leer_accesos()
        if df is None or df.empty:
            st.caption("Todavía no hay accesos.")
        else:
            st.dataframe(df.iloc[::-1].head(12)[["fecha_hora", "placa", "estado", "fuente"]],
                         hide_index=True, width="stretch")


with tab_vivo:
    en_vivo()

# ---------------------------------------------------------------- leer
with tab_leer:
    fuente = st.radio("Fuente", ["Foto", "Video", "Cámara (IP/RTSP o USB)"], horizontal=True)
    autorizadas = cargar_autorizadas()

    if fuente == "Foto":
        archivos = st.file_uploader("Sube una o varias fotos", type=["jpg", "jpeg", "png"],
                                    accept_multiple_files=True)
        for arch in archivos or []:
            datos = arch.getvalue()
            frame = cv2.imdecode(np.frombuffer(datos, np.uint8), cv2.IMREAD_COLOR)
            t0 = time.time()
            lecturas = motor.leer(alpr(), frame, reglas)
            ms = (time.time() - t0) * 1000
            c1, c2 = st.columns([3, 2])
            c1.image(a_rgb(motor.dibujar(frame, lecturas, autorizadas)), caption=arch.name,
                     width="stretch")
            with c2:
                if lecturas:
                    for f in lecturas:
                        e = motor.estado(f["placa"], autorizadas)
                        icono = {"Autorizada": "✅", "No registrada": "⛔"}.get(e, "🔎")
                        st.metric(f"{icono} {e}", f["placa"], f"confianza {f['conf_ocr']:.0%}",
                                  delta_color="off")
                    if st.button("Registrar acceso", key=f"reg_{arch.name}"):
                        for f in lecturas:
                            registrar(f, frame, f"foto {arch.name}")
                        st.success("Registrado.")
                else:
                    st.warning("No se encontró ninguna placa legible.")
                st.caption(f"Tiempo de lectura: {ms:.0f} ms")

    elif fuente == "Video":
        arch = st.file_uploader("Sube un video", type=["mp4", "avi", "mov", "mkv"])
        guardar = st.checkbox("Guardar las placas confirmadas en el registro de accesos", value=True)
        if arch and st.button("Analizar video", type="primary"):
            with tempfile.NamedTemporaryFile(suffix=os.path.splitext(arch.name)[1], delete=False) as tmp:
                tmp.write(arch.getvalue())
            cap = cv2.VideoCapture(tmp.name)
            fps = cap.get(cv2.CAP_PROP_FPS) or 30
            total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 1
            conf = motor.Confirmador(espera_s=espera)
            barra = st.progress(0.0, text="Analizando...")
            c1, c2 = st.columns([3, 2])
            vista, lista = c1.empty(), c2.empty()
            eventos, i, inicio = [], 0, datetime.now()
            while True:
                ok, frame = cap.read()
                if not ok:
                    break
                if i % cada == 0:
                    t = i / fps
                    lecturas = motor.leer(alpr(), frame, reglas)
                    for f in lecturas:
                        f["cuadro"], f["t"] = frame, t
                    for f in conf.agregar(lecturas, t):
                        eventos.append(evento_video(f, arch.name, guardar, autorizadas))
                    vista.image(a_rgb(motor.dibujar(frame, lecturas, autorizadas)), width="stretch")
                    with lista.container():
                        st.subheader(f"Placas confirmadas: {len(eventos)}")
                        tabla_eventos(eventos)
                    barra.progress(min(i / total, 1.0), text=f"Analizando... {t:.0f} s de {total / fps:.0f} s")
                i += 1
            for f in conf.terminar(i / fps):
                eventos.append(evento_video(f, arch.name, guardar, autorizadas))
            with lista.container():
                st.subheader(f"Placas confirmadas: {len(eventos)}")
                tabla_eventos(eventos)
            barra.progress(1.0, text=f"Listo: {len(eventos)} placas confirmadas en "
                                     f"{(datetime.now() - inicio).seconds} s de análisis.")
            os.unlink(tmp.name)

    else:
        st.caption("Ejemplos: `rtsp://usuario:clave@192.168.1.64:554/Streaming/Channels/101` "
                   "(cámara IP) o `0` (cámara USB del PC).")
        url = st.text_input("Dirección de la cámara", value=st.session_state.get("url_camara", ""))
        st.session_state["url_camara"] = url
        c_ini, c_fin = st.columns(2)
        iniciar = c_ini.button("Iniciar", type="primary", disabled=not url)
        c_fin.button("Detener")  # cualquier clic reinicia la página y corta el ciclo
        if iniciar:
            cap = cv2.VideoCapture(int(url) if url.isdigit() else url)
            if not cap.isOpened():
                st.error("No se pudo abrir la cámara. Revisa la dirección, el usuario y la clave, "
                         "y que el PC esté en la misma red que la cámara.")
            else:
                conf = motor.Confirmador(espera_s=espera)
                c1, c2 = st.columns([3, 2])
                vista, lista = c1.empty(), c2.empty()
                eventos, fallos = [], 0
                while True:
                    ok, frame = cap.read()
                    if not ok:
                        fallos += 1
                        if fallos > 50:
                            st.error("Se perdió la señal de la cámara.")
                            break
                        continue
                    fallos = 0
                    lecturas = motor.leer(alpr(), frame, reglas)
                    for f in lecturas:
                        f["cuadro"] = frame
                    for f in conf.agregar(lecturas):
                        eventos.insert(0, registrar(f, f["cuadro"], "cámara"))
                    vista.image(a_rgb(motor.dibujar(frame, lecturas, autorizadas)), width="stretch")
                    with lista.container():
                        st.subheader("Últimos accesos")
                        tabla_eventos(eventos[:15])
                    # Descarta cuadros acumulados para mostrar siempre lo más reciente
                    for _ in range(2):
                        cap.grab()

# ---------------------------------------------------------------- registro
@st.fragment(run_every=5)
def tabla_registro(buscar, tipo):
    df = leer_accesos()
    if df is None:
        st.info("Aún no hay accesos registrados. Lee una foto, un video o conecta una cámara.")
        return
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Accesos registrados", len(df))
    c2.metric("Carros", int((df["tipo"] == "Carro").sum()))
    c3.metric("Motos", int((df["tipo"] == "Moto").sum()))
    c4.metric("Autorizados", int((df["estado"] == "Autorizada").sum()))
    c5.metric("No registrados", int((df["estado"] == "No registrada").sum()))
    vista_df = df[df["placa"].str.contains(buscar, na=False)] if buscar else df
    if tipo != "Todos":
        vista_df = vista_df[vista_df["tipo"] == tipo]
    vista_df = vista_df.iloc[::-1].reset_index(drop=True)
    st.caption("Toca una fila para ver la foto de evidencia.")
    sel = st.dataframe(vista_df.drop(columns=["captura"]), hide_index=True, width="stretch",
                       on_select="rerun", selection_mode="single-row", key="tabla_accesos")
    st.download_button("Descargar registro (CSV)", df.to_csv(index=False).encode(), "accesos.csv", "text/csv")
    if len(vista_df):
        filas = sel.selection.rows
        fila = vista_df.iloc[filas[0] if filas else 0]
        ruta = os.path.join(registro.CAPTURAS, str(fila["captura"]))
        st.subheader(f"Evidencia: {fila['placa']} ({fila['tipo']}) · {fila['fecha_hora']}")
        if os.path.exists(ruta):
            st.image(ruta, caption=f"{fila['estado']} · confianza {fila['confianza']} · {fila['fuente']}")
        else:
            st.caption("La foto de este registro ya no está en el servidor.")


with tab_registro:
    f1, f2 = st.columns([2, 1])
    buscar = f1.text_input("Buscar placa").strip().upper()
    tipo = f2.selectbox("Tipo de vehículo", ["Todos", "Carro", "Moto", "Otro"])
    tabla_registro(buscar, tipo)
    if os.path.exists(registro.ARCH_ACCESOS) and st.button("Borrar registro"):
        os.remove(registro.ARCH_ACCESOS)
        st.rerun()

# ---------------------------------------------------------------- autorizadas
with tab_autorizadas:
    st.write("Escribe una placa por línea. Las placas de esta lista salen en verde; las demás, en rojo. "
             "Si la lista está vacía, solo se leen las placas sin clasificarlas.")
    actuales = "\n".join(sorted(cargar_autorizadas()))
    texto = st.text_area("Placas autorizadas", value=actuales, height=260, placeholder="AB123CD\nXYZ12A")
    if st.button("Guardar lista", type="primary"):
        placas = {registro.limpiar_placa(l) for l in texto.splitlines() if l.strip()}
        registro.guardar_autorizadas(placas)
        st.success(f"Lista guardada: {len(placas)} placas.")
