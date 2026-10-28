# Escribe una funcion llamada cargar_datos que reciba
# una ruta a un archivo CSV y devuelva un DataFrame de pandas.
# La funcion debe:
# - Verificar que el archivo existe.
# - Leer el CSV con pandas.
# - Convertir la columna ’fecha’ a tipo datetime.
# - Devolver el DataFrame limpio.
# - Incluir comentarios en espanol.
def cargar_datos(ruta_archivo):
    import os
    import pandas as pd

    # Verificar que el archivo existe
    if not os.path.exists(ruta_archivo):
        raise FileNotFoundError(f"El archivo {ruta_archivo} no existe.")

    # Leer el CSV con pandas
    df = pd.read_csv(ruta_archivo)

    # Convertir la columna 'fecha' a tipo datetime
    if 'fecha' in df.columns:
        df['fecha'] = pd.to_datetime(df['fecha'], errors='coerce')
    else:
        raise KeyError("La columna 'fecha' no se encuentra en el DataFrame.")

    # Devolver el DataFrame limpio
    return df

if __name__ == "__main__":
    df = cargar_datos("../data/raw/habitos.csv")
    print(df)
    print(df.describe())

# True Sunrise, plataforma de transparencia financiera universitaria. Módulo de carga y limpieza con pandas.
# Esquema de data/raw/movimientos.csv:
# fecha (YYYY-MM-DD), tipo ("ingreso" o "gasto"), categoria (ej. "Transporte escolar", "Obras de infraestructura"),
# concepto (str), monto (float > 0), monto_presupuestado (float, solo gastos, puede venir vacío),
# responsable (str), cargo (str), estado_aprobacion ("aprobado", "pendiente", "rechazado").
#
# Implementa:
# 1. cargar_movimientos(ruta: str) -> pd.DataFrame
#    Convierte fecha a datetime y montos a float.
#    Casos borde: archivo inexistente -> FileNotFoundError en español. CSV vacío -> DataFrame vacío con todas las columnas.
#    Columnas faltantes -> ValueError listando cuáles. Fechas o montos no numéricos -> errors="coerce",
#    descartar filas y avisar con warnings.warn cuántas se eliminaron.
# 2. limpiar_movimientos(df) -> pd.DataFrame
#    Normaliza tipo y estado_aprobacion a minúsculas, aplica strip a textos. Filas con tipo distinto de ingreso o gasto
#    se descartan con warning. Montos negativos o cero se descartan. responsable o cargo vacíos se rellenan con
#    "Sin responsable registrado" (no eliminar, es una señal de opacidad). No modifica el df original.
# 3. filtrar_movimientos(df, fecha_inicio=None, fecha_fin=None, categorias=None, tipo=None) -> pd.DataFrame
#    Filtros opcionales. fecha_inicio > fecha_fin -> ValueError. Lista vacía equivale a no filtrar.
#    Sin coincidencias -> df vacío con mismas columnas.
# Type hints, docstrings estilo Google en español y comentarios en español.

from datetime import date
from typing import Optional, Sequence, Union
import warnings

import pandas as pd


COLUMNAS_MOVIMIENTOS = [
    "fecha",
    "tipo",
    "categoria",
    "concepto",
    "monto",
    "monto_presupuestado",
    "responsable",
    "cargo",
    "estado_aprobacion",
]


def cargar_movimientos(ruta: str) -> pd.DataFrame:
    """Carga movimientos desde un CSV y descarta filas con datos inválidos.

    Args:
        ruta: Ruta del archivo CSV.

    Returns:
        DataFrame con fechas y montos convertidos a sus tipos correspondientes.

    Raises:
        FileNotFoundError: Si el archivo no existe.
        ValueError: Si faltan columnas requeridas.
    """
    import os

    if not os.path.exists(ruta):
        raise FileNotFoundError(f"El archivo {ruta} no existe.")

    try:
        df = pd.read_csv(ruta)
    except pd.errors.EmptyDataError:
        # Un archivo completamente vacío conserva el esquema esperado.
        return pd.DataFrame(columns=COLUMNAS_MOVIMIENTOS)

    faltantes = [columna for columna in COLUMNAS_MOVIMIENTOS if columna not in df.columns]
    if faltantes:
        raise ValueError(f"Faltan las siguientes columnas requeridas: {', '.join(faltantes)}")

    if df.empty:
        return df[COLUMNAS_MOVIMIENTOS].copy()

    # Se guarda el texto original para distinguir presupuestos vacíos de valores inválidos.
    presupuesto_original = df["monto_presupuestado"]
    df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce")
    df["monto"] = pd.to_numeric(df["monto"], errors="coerce")
    df["monto_presupuestado"] = pd.to_numeric(
        presupuesto_original, errors="coerce"
    )

    presupuesto_invalido = (
        presupuesto_original.notna()
        & presupuesto_original.astype(str).str.strip().ne("")
        & df["monto_presupuestado"].isna()
    )
    filas_invalidas = (
        df["fecha"].isna()
        | df["monto"].isna()
        | presupuesto_invalido
    )
    cantidad_eliminada = int(filas_invalidas.sum())
    if cantidad_eliminada:
        warnings.warn(
            f"Se eliminaron {cantidad_eliminada} filas por fechas o montos inválidos.",
            UserWarning,
            stacklevel=2,
        )

    return df.loc[~filas_invalidas, COLUMNAS_MOVIMIENTOS].copy()


def limpiar_movimientos(df: pd.DataFrame) -> pd.DataFrame:
    """Normaliza los campos de movimientos y elimina registros no válidos.

    Args:
        df: DataFrame de movimientos que se limpiará.

    Returns:
        Una copia limpia del DataFrame; el original no se modifica.
    """
    limpio = df.copy()

    # Quitar espacios de los campos textuales sin convertir valores nulos en texto.
    columnas_texto = [
        "tipo", "categoria", "concepto", "responsable", "cargo", "estado_aprobacion"
    ]
    for columna in columnas_texto:
        if columna in limpio.columns:
            limpio[columna] = limpio[columna].map(
                lambda valor: valor.strip() if isinstance(valor, str) else valor
            )

    if "tipo" in limpio.columns:
        limpio["tipo"] = limpio["tipo"].map(
            lambda valor: valor.lower() if isinstance(valor, str) else valor
        )
        tipo_valido = limpio["tipo"].isin(["ingreso", "gasto"])
        cantidad_tipo_invalido = int((~tipo_valido).sum())
        if cantidad_tipo_invalido:
            warnings.warn(
                f"Se descartaron {cantidad_tipo_invalido} filas con un tipo inválido.",
                UserWarning,
                stacklevel=2,
            )
        limpio = limpio.loc[tipo_valido].copy()

    if "estado_aprobacion" in limpio.columns:
        limpio["estado_aprobacion"] = limpio["estado_aprobacion"].map(
            lambda valor: valor.lower() if isinstance(valor, str) else valor
        )

    # Los datos de responsable y cargo ausentes son señales de opacidad, no motivo de descarte.
    for columna in ("responsable", "cargo"):
        if columna in limpio.columns:
            vacio = limpio[columna].isna() | limpio[columna].eq("")
            limpio.loc[vacio, columna] = "Sin responsable registrado"

    if "monto" in limpio.columns:
        limpio["monto"] = pd.to_numeric(limpio["monto"], errors="coerce")
        limpio = limpio.loc[limpio["monto"].gt(0)].copy()
    if "monto_presupuestado" in limpio.columns:
        limpio["monto_presupuestado"] = pd.to_numeric(
            limpio["monto_presupuestado"], errors="coerce"
        )

    return limpio


def filtrar_movimientos(
    df: pd.DataFrame,
    fecha_inicio: Optional[Union[str, date, pd.Timestamp]] = None,
    fecha_fin: Optional[Union[str, date, pd.Timestamp]] = None,
    categorias: Optional[Sequence[str]] = None,
    tipo: Optional[str] = None,
) -> pd.DataFrame:
    """Filtra movimientos por fechas, categorías y tipo.

    Args:
        df: DataFrame que se filtrará.
        fecha_inicio: Fecha mínima inclusiva.
        fecha_fin: Fecha máxima inclusiva.
        categorias: Categorías permitidas; una lista vacía no aplica filtro.
        tipo: Tipo de movimiento permitido.

    Returns:
        Una copia de las filas coincidentes, conservando las columnas originales.

    Raises:
        ValueError: Si la fecha de inicio es posterior a la fecha de fin.
    """
    inicio = pd.to_datetime(fecha_inicio) if fecha_inicio is not None else None
    fin = pd.to_datetime(fecha_fin) if fecha_fin is not None else None
    if inicio is not None and fin is not None and inicio > fin:
        raise ValueError("La fecha de inicio no puede ser posterior a la fecha de fin.")

    resultado = df.copy()
    if "fecha" in resultado.columns and (inicio is not None or fin is not None):
        fechas = pd.to_datetime(resultado["fecha"], errors="coerce")
        if inicio is not None:
            resultado = resultado.loc[fechas >= inicio]
            fechas = fechas.loc[resultado.index]
        if fin is not None:
            resultado = resultado.loc[fechas <= fin]

    if categorias and "categoria" in resultado.columns:
        resultado = resultado.loc[resultado["categoria"].isin(categorias)]
    if tipo is not None and "tipo" in resultado.columns:
        resultado = resultado.loc[
            resultado["tipo"].astype("string").str.strip().str.lower() == tipo.strip().lower()
        ]

    return resultado.copy()
