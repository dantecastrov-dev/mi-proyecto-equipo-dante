# True Sunrise. Autenticación para Streamlit con bcrypt. Requerimiento de seguridad prioritario.
# Usuarios en st.secrets["usuarios"] con formato {usuario: {"hash": str, "nombre": str, "rol": str}}.
# Nunca guardes ni registres contraseñas en texto plano.

import time
from collections.abc import Mapping
from typing import Any

import bcrypt
import streamlit as st


def verificar_credenciales(usuario: str, contrasena: str, usuarios: dict) -> bool:
	"""Comprueba las credenciales sin revelar si el usuario existe."""
	if not usuario or not contrasena or not isinstance(usuarios, Mapping):
		return False

	datos = usuarios.get(usuario)
	if not isinstance(datos, Mapping):
		return False

	hash_guardado = datos.get("hash")
	if not isinstance(hash_guardado, str):
		return False

	try:
		return bcrypt.checkpw(contrasena.encode("utf-8"), hash_guardado.encode("ascii"))
	except (ValueError, TypeError, UnicodeEncodeError):
		# Un hash inválido se considera siempre una autenticación fallida.
		return False


def render_login() -> bool:
	"""Renderiza el formulario de acceso y administra los intentos fallidos."""
	estado = st.session_state
	estado.setdefault("autenticado", False)
	estado.setdefault("_intentos_login", 0)
	estado.setdefault("_bloqueo_login_hasta", 0.0)

	if estado["autenticado"]:
		return True

	ahora = time.time()
	if ahora >= estado["_bloqueo_login_hasta"]:
		estado["_intentos_login"] = 0
		estado["_bloqueo_login_hasta"] = 0.0
	bloqueado_hasta = estado["_bloqueo_login_hasta"]
	bloqueado = ahora < bloqueado_hasta

	with st.form("formulario_login"):
		usuario = st.text_input("Usuario", disabled=bloqueado)
		contrasena = st.text_input("Contraseña", type="password", disabled=bloqueado)
		enviado = st.form_submit_button("Iniciar sesión", disabled=bloqueado)

	if bloqueado:
		restante = max(1, int(bloqueado_hasta - ahora))
		st.warning(f"Demasiados intentos. Inténtalo de nuevo en {restante} segundos.")
		return False

	if enviado:
		usuarios: Any = st.secrets.get("usuarios", {})
		if verificar_credenciales(usuario, contrasena, usuarios):
			datos = usuarios[usuario]
			estado["autenticado"] = True
			estado["usuario"] = usuario
			estado["nombre"] = datos.get("nombre", usuario)
			estado["rol"] = datos.get("rol", "")
			estado["_intentos_login"] = 0
			estado["_bloqueo_login_hasta"] = 0.0
			return True

		estado["_intentos_login"] += 1
		if estado["_intentos_login"] >= 5:
			estado["_bloqueo_login_hasta"] = time.time() + 5 * 60
		st.error("Credenciales inválidas")

	return False


def cerrar_sesion() -> None:
	"""Limpia los datos de sesión y reinicia la aplicación."""
	st.session_state.clear()
	st.rerun()


def generar_hash(contrasena: str) -> str:
	"""Genera un hash bcrypt para crear credenciales desde consola."""
	return bcrypt.hashpw(contrasena.encode("utf-8"), bcrypt.gensalt()).decode("ascii")