"""App de demo: control de acceso vehicular por lectura de placas venezolanas.

Ejecutar:  streamlit run app.py
Luego abrir http://localhost:8501 en el navegador.
"""
import base64
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
from reglas_venezuela import tipo

ICONO_TIPO = {"Carro": "🚗", "Moto": "🏍️"}

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


def con_tipo(df):
    """Agrega la columna tipo (Carro / Moto) al lado de la placa, según su formato."""
    df = df.copy()
    df.insert(df.columns.get_loc("placa") + 1, "tipo", df["placa"].map(tipo))
    return df


def tabla_eventos(eventos):
    if eventos:
        st.dataframe(con_tipo(pd.DataFrame(eventos))[["fecha_hora", "placa", "tipo", "estado", "confianza"]],
                     hide_index=True, width="stretch")
    else:
        st.caption("Todavía no se ha confirmado ninguna placa.")


# ---------------------------------------------------------------- barra lateral
with st.sidebar:
    st.header("Ajustes")
    reglas = st.toggle("Solo placas venezolanas", value=True,
                       help="Corrige confusiones como O/0 o B/8 y descarta textos que no son placas "
                            "venezolanas (carros AB123CD, ABC12D, ABC123; motos AB1C23D). Apágalo para probar con placas de otros países.")
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
        return pd.read_csv(registro.ARCH_ACCESOS)
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
            st.dataframe(con_tipo(df.iloc[::-1].head(12))[["fecha_hora", "placa", "tipo", "estado", "fuente"]],
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
                        t = tipo(f["placa"])
                        st.metric(f"{icono} {e} · {ICONO_TIPO.get(t, '')} {t}", f["placa"], f"confianza {f['conf_ocr']:.0%}",
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
@st.cache_data(max_entries=2000, show_spinner=False)
def miniatura(nombre):
    """Foto de evidencia en pequeño para la tabla (las capturas no cambian: se calcula una vez)."""
    img = cv2.imread(os.path.join(registro.CAPTURAS, str(nombre)))
    if img is None:
        return None
    alto = 120
    img = cv2.resize(img, (int(img.shape[1] * alto / img.shape[0]), alto), interpolation=cv2.INTER_AREA)
    ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 70])
    return "data:image/jpeg;base64," + base64.b64encode(buf).decode() if ok else None


@st.fragment(run_every=5)
def tabla_registro(buscar, filtro_tipo):
    df = leer_accesos()
    if df is None:
        st.info("Aún no hay accesos registrados. Lee una foto, un video o conecta una cámara.")
        return
    df = con_tipo(df)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Accesos registrados", len(df))
    c2.metric("🚗 Carros", int((df["tipo"] == "Carro").sum()))
    c3.metric("🏍️ Motos", int((df["tipo"] == "Moto").sum()))
    c4.metric("No registrados", int((df["estado"] == "No registrada").sum()))
    vista_df = df[df["placa"].str.contains(buscar, na=False)] if buscar else df
    if filtro_tipo != "Todos":
        vista_df = vista_df[vista_df["tipo"] == filtro_tipo.rstrip("s")]
    vista_df = vista_df.iloc[::-1]
    tabla = vista_df.copy()
    tabla.insert(0, "evidencia", tabla["captura"].map(miniatura))
    st.dataframe(tabla.drop(columns=["captura"]), hide_index=True, width="stretch", row_height=70,
                 column_config={"evidencia": st.column_config.ImageColumn("Evidencia", width="small")})
    st.download_button("Descargar registro (CSV)", df.to_csv(index=False).encode(), "accesos.csv", "text/csv")

    # Foto completa de un acceso, para ver la placa en grande o guardarla como evidencia
    opciones = {f"{f.fecha_hora} · {f.placa} · {f.tipo}": f for f in vista_df.head(200).itertuples()}
    if opciones:
        st.subheader("Evidencia fotográfica")
        elegido = st.selectbox("Acceso", list(opciones), key="evidencia_elegida")
        fila = opciones[elegido]
        ruta = os.path.join(registro.CAPTURAS, str(fila.captura))
        if os.path.exists(ruta):
            c1, c2 = st.columns([3, 1])
            c1.image(ruta, width="stretch")
            c2.metric(f"{ICONO_TIPO.get(fila.tipo, '')} {fila.tipo}", fila.placa)
            c2.caption(f"{fila.fecha_hora}  \n{fila.estado} · confianza {fila.confianza}  \nFuente: {fila.fuente}")
            with open(ruta, "rb") as fh:
                c2.download_button("Descargar foto", fh.read(), str(fila.captura), "image/jpeg")
        else:
            st.caption("La foto de este acceso ya no está guardada.")


with tab_registro:
    c_buscar, c_tipo = st.columns([3, 2])
    buscar = c_buscar.text_input("Buscar placa").strip().upper()
    filtro_tipo = c_tipo.segmented_control("Tipo de vehículo", ["Todos", "Carros", "Motos"],
                                           default="Todos") or "Todos"
    tabla_registro(buscar, filtro_tipo)
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
