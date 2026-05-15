import io

import requests
import streamlit as st
from PIL import Image

from ui.config import API
from ui.components import page_header


def page_clients():
    page_header("Clientes", "Buscar Cliente")

    try:
        resp = requests.get(f"{API}/clients/")
        if resp.status_code != 200:
            st.error(f"Error al obtener clientes: {resp.text}")
            return
        clients = resp.json()
    except requests.exceptions.ConnectionError:
        st.error("No se puede conectar al servidor. Asegúrate de que FastAPI esté corriendo.")
        return

    if not clients:
        st.info("No hay clientes registrados aún.")
        return

    st.markdown(
        f'<div class="count-tag">{len(clients)} cliente(s) registrado(s)</div>',
        unsafe_allow_html=True,
    )

    for client in clients:
        with st.expander(
            f"  {client['nombre_completo']}   ·   CURP: {client['curp']}",
            expanded=False,
        ):
            img_col, info_col = st.columns([2, 3])
            with img_col:
                cid = client["client_id"]
                front_resp = requests.get(f"{API}/clients/image/{cid}/front")
                if front_resp.status_code == 200:
                    front_img = Image.open(io.BytesIO(front_resp.content))
                    st.image(front_img, caption="Frente del INE", use_container_width=True)
                else:
                    st.warning("Imagen del frente no disponible")
                back_resp = requests.get(f"{API}/clients/image/{cid}/back")
                if back_resp.status_code == 200:
                    back_img = Image.open(io.BytesIO(back_resp.content))
                    st.image(back_img, caption="Reverso del INE", use_container_width=True)
                else:
                    st.warning("Imagen del reverso no disponible")
            with info_col:
                fields = [
                    ("ID Cliente",          client["client_id"]),
                    ("Nombre Completo",      client["nombre_completo"]),
                    ("CURP",                client["curp"]),
                    ("Clave de Elector",    client["clave_de_elector"]),
                    ("Fecha de Nacimiento", client["fecha_nacimiento"]),
                    ("Domicilio",           client["domicilio"]),
                    ("Registrado",          client["registered_at"]),
                ]
                for label, value in fields:
                    st.markdown(f"""
                    <div style="margin-bottom:0.9rem;">
                        <div class="field-label">{label}</div>
                        <div class="field-value">{value or '—'}</div>
                    </div>
                    """, unsafe_allow_html=True)
