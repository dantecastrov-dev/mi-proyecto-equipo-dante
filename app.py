import streamlit as st
st.title("Mi Impacto Personal")
st.write("Bienvenido a tu primera aplicación.")
st.write("Aquí registraremos tus habitos diarios.")

nombre = st.text_input("Escribe tu nombre:")
if nombre:
    st.write(f"Hola, {nombre}! Que bueno verte.")