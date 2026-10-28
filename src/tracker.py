"""Módulo de trazabilidad financiera para True Sunrise.

Este módulo recibe DataFrames limpios generados por ``src/data_processor.py`` y
realiza cálculos de lectura únicamente. Las funciones son puras y no modifican
el DataFrame de entrada.

Ejemplos de uso:
    >>> df = pd.DataFrame({
    ...     "tipo": ["ingreso", "gasto", "gasto"],
    ...     "monto": [1000.0, 300.0, 200.0],
    ...     "categoria": ["ventas", "operacion", "marketing"],
    ... })
    >>> calcular_balance_general(df)
    {'total_ingresos': 1000.0, 'total_gastos': 500.0, 'balance': 500.0,
     'porcentaje_gastado': 0.5}
"""

from __future__ import annotations

from typing import Any

import pandas as pd


def calcular_balance_general(df: pd.DataFrame) -> dict[str, float | None]:
    """Calcula el balance general de ingresos y gastos.

    Args:
        df: DataFrame con columnas relevantes como ``tipo`` y ``monto``.

    Returns:
        Un diccionario con:
        - total_ingresos
        - total_gastos
        - balance
        - porcentaje_gastado = gastos / ingresos, o None si ingresos == 0

    Ejemplo:
        >>> df = pd.DataFrame({"tipo": ["ingreso", "gasto", "gasto"],
        ...                   "monto": [1000, 200, 300]})
        >>> calcular_balance_general(df)
        {'total_ingresos': 1000.0, 'total_gastos': 500.0, 'balance': 500.0,
         'porcentaje_gastado': 0.5}
    """
    if df.empty:
        return {
            "total_ingresos": 0.0,
            "total_gastos": 0.0,
            "balance": 0.0,
            "porcentaje_gastado": 0.0,
        }

    if "tipo" not in df.columns or "monto" not in df.columns:
        total_ingresos = 0.0
        total_gastos = 0.0
    else:
        total_ingresos = float(df.loc[df["tipo"].astype(str).str.lower() == "ingreso", "monto"].sum())
        total_gastos = float(df.loc[df["tipo"].astype(str).str.lower() == "gasto", "monto"].sum())

    balance = total_ingresos - total_gastos
    porcentaje_gastado = None if total_ingresos == 0 else total_gastos / total_ingresos

    return {
        "total_ingresos": total_ingresos,
        "total_gastos": total_gastos,
        "balance": balance,
        "porcentaje_gastado": porcentaje_gastado,
    }


def gastos_por_categoria(df: pd.DataFrame) -> pd.DataFrame:
    """Agrupa gastos por categoría y compara contra su presupuesto.

    La salida contiene las columnas:
    ``categoria, gasto_real, presupuestado, desviacion, desviacion_pct``.
    Si una categoría no tiene presupuesto, ``presupuestado`` será NaN y la
    desviación porcentual será ``None``. Si no hay gastos, retorna un DataFrame
    vacío con esas columnas.

    Args:
        df: DataFrame con columnas como ``categoria``, ``monto``, ``tipo`` y
            ``monto_presupuestado`` o un presupuesto equivalente.

    Returns:
        DataFrame ordenado por ``desviacion_pct`` descendente.
    """
    columnas_esperadas = ["categoria", "gasto_real", "presupuestado", "desviacion", "desviacion_pct"]

    if df.empty:
        return pd.DataFrame(columns=columnas_esperadas)

    if "tipo" in df.columns:
        gastos = df.loc[df["tipo"].astype(str).str.lower() == "gasto"].copy()
    else:
        gastos = df.copy()

    if gastos.empty:
        return pd.DataFrame(columns=columnas_esperadas)

    if "categoria" not in gastos.columns:
        return pd.DataFrame(columns=columnas_esperadas)

    if "monto" not in gastos.columns:
        return pd.DataFrame(columns=columnas_esperadas)

    categorias = gastos.groupby("categoria", dropna=False)["monto"].sum().reset_index(name="gasto_real")

    presupuesto_col = "monto_presupuestado" if "monto_presupuestado" in df.columns else "presupuesto"
    if presupuesto_col in df.columns:
        presupuesto = (
            df.groupby("categoria", dropna=False)[presupuesto_col].sum().reset_index(name="presupuestado")
        )
        resumen = categorias.merge(presupuesto, on="categoria", how="outer")
    else:
        resumen = categorias.copy()
        resumen["presupuestado"] = pd.NA

    resumen["desviacion"] = resumen["gasto_real"] - resumen["presupuestado"]
    resumen["desviacion_pct"] = None

    mask_presupuesto = resumen["presupuestado"].notna() & (resumen["presupuestado"] != 0)
    resumen.loc[mask_presupuesto, "desviacion_pct"] = (
        resumen.loc[mask_presupuesto, "desviacion"] / resumen.loc[mask_presupuesto, "presupuestado"]
    )

    resumen["presupuestado"] = pd.to_numeric(resumen["presupuestado"], errors="coerce")
    resumen["desviacion"] = pd.to_numeric(resumen["desviacion"], errors="coerce")
    resumen["desviacion_pct"] = pd.to_numeric(resumen["desviacion_pct"], errors="coerce")

    resumen = resumen[["categoria", "gasto_real", "presupuestado", "desviacion", "desviacion_pct"]]
    resumen = resumen.sort_values(by="desviacion_pct", ascending=False, na_position="last")
    resumen = resumen.reset_index(drop=True)
    return resumen


def detectar_ineficiencias(df: pd.DataFrame, umbral_pct: float = 10.0) -> pd.DataFrame:
    """Detecta gastos ineficientes o con responsables faltantes.

    Se consideran ineficientes los gastos cuyo monto supera el monto presupuestado
    por más del umbral especificado. También se reportan gastos con responsable
    igual a "Sin responsable registrado".

    Args:
        df: DataFrame con columnas de gastos, presupuesto y responsable.
        umbral_pct: porcentaje mínimo de sobreprecio requerido para marcar un
            movimiento como ineficiente. Si es negativo, se lanza ValueError.

    Returns:
        DataFrame con columnas: ``categoria, monto, monto_presupuestado, diferencia,
        porcentaje_sobreprecio, responsable, motivo``.

    Raises:
        ValueError: si ``umbral_pct`` es negativo.
    """
    if umbral_pct < 0:
        raise ValueError("umbral_pct no puede ser negativo.")

    if df.empty:
        return pd.DataFrame(columns=[
            "categoria",
            "monto",
            "monto_presupuestado",
            "diferencia",
            "porcentaje_sobreprecio",
            "responsable",
            "motivo",
        ])

    datos = df.copy()
    required = {"categoria", "monto", "monto_presupuestado", "responsable"}
    if not required.issubset(datos.columns):
        return pd.DataFrame(columns=[
            "categoria",
            "monto",
            "monto_presupuestado",
            "diferencia",
            "porcentaje_sobreprecio",
            "responsable",
            "motivo",
        ])

    datos["diferencia"] = pd.to_numeric(datos["monto"], errors="coerce") - pd.to_numeric(
        datos["monto_presupuestado"], errors="coerce"
    )
    datos["porcentaje_sobreprecio"] = None
    mask = datos["monto_presupuestado"].notna() & (datos["monto_presupuestado"] != 0)
    datos.loc[mask, "porcentaje_sobreprecio"] = (
        datos.loc[mask, "diferencia"] / datos.loc[mask, "monto_presupuestado"]
    ) * 100.0

    sobreprecio = datos.loc[
        (datos["porcentaje_sobreprecio"].notna())
        & (datos["porcentaje_sobreprecio"] > umbral_pct)
    ].copy()
    sobreprecio["motivo"] = "Sobreprecio"

    sin_responsable = datos.loc[
        datos["responsable"].astype(str).str.lower().eq("sin responsable registrado")
    ].copy()
    sin_responsable["motivo"] = "Sin responsable"

    resultado = pd.concat([sobreprecio, sin_responsable], ignore_index=True)

    columnas_finales = [
        "categoria",
        "monto",
        "monto_presupuestado",
        "diferencia",
        "porcentaje_sobreprecio",
        "responsable",
        "motivo",
    ]
    return resultado[columnas_finales]


def obtener_responsables(df: pd.DataFrame, categoria: str | None = None) -> pd.DataFrame:
    """Obtiene el resumen de responsables por categoría.

    Filtra solo movimientos en estado ``aprobado`` y devuelve una agregación de
    responsables con sus movimientos y monto total aprobados.

    Args:
        df: DataFrame con columnas ``responsable``, ``cargo``, ``estado`` y
            ``monto``. Además puede incluir ``categoria``.
        categoria: Si se especifica, se filtra esa categoría; si no existe,
            devuelve un DataFrame vacío con las columnas esperadas.

    Returns:
        DataFrame con columnas:
        ``responsable, cargo, movimientos_aprobados, monto_total_aprobado``.
    """
    columnas = ["responsable", "cargo", "movimientos_aprobados", "monto_total_aprobado"]

    if df.empty:
        return pd.DataFrame(columns=columnas)

    datos = df.copy()
    if categoria is not None:
        if "categoria" not in datos.columns:
            return pd.DataFrame(columns=columnas)
        datos = datos.loc[datos["categoria"].astype(str).str.lower() == categoria.lower()]
        if datos.empty:
            return pd.DataFrame(columns=columnas)

    if not {"responsable", "cargo", "estado", "monto"}.issubset(datos.columns):
        return pd.DataFrame(columns=columnas)

    aprobados = datos.loc[datos["estado"].astype(str).str.lower() == "aprobado"].copy()
    if aprobados.empty:
        return pd.DataFrame(columns=columnas)

    resultado = (
        aprobados.groupby(["responsable", "cargo"], dropna=False)
        .agg(movimientos_aprobados=("monto", "size"), monto_total_aprobado=("monto", "sum"))
        .reset_index()
    )
    return resultado[columnas]


def tendencia_mensual(df: pd.DataFrame) -> pd.DataFrame:
    """Calcula la tendencia mensual de ingresos, gastos y balance.

    Se asume que el DataFrame incluye columnas ``fecha`` o ``mes`` y ``tipo`` y
    ``monto``. Si un mes no tiene movimientos, se representa en 0.

    Args:
        df: DataFrame con movimientos financieros.

    Returns:
        DataFrame con columnas ``mes, ingresos, gastos, balance`` ordenado por
        fecha/mes.
    """
    columnas = ["mes", "ingresos", "gastos", "balance"]

    if df.empty:
        return pd.DataFrame(columns=columnas)

    datos = df.copy()

    if "fecha" in datos.columns:
        datos["mes"] = pd.to_datetime(datos["fecha"], errors="coerce").dt.to_period("M").astype(str)
    elif "mes" in datos.columns:
        datos["mes"] = datos["mes"].astype(str)
    else:
        return pd.DataFrame(columns=columnas)

    if not {"tipo", "monto"}.issubset(datos.columns):
        return pd.DataFrame(columns=columnas)

    datos["monto"] = pd.to_numeric(datos["monto"], errors="coerce")
    datos["tipo"] = datos["tipo"].astype(str).str.lower()

    ingresos = (
        datos.loc[datos["tipo"] == "ingreso", ["mes", "monto"]]
        .groupby("mes", as_index=False)["monto"].sum()
        .rename(columns={"monto": "ingresos"})
    )
    gastos = (
        datos.loc[datos["tipo"] == "gasto", ["mes", "monto"]]
        .groupby("mes", as_index=False)["monto"].sum()
        .rename(columns={"monto": "gastos"})
    )

    resumen = ingresos.merge(gastos, on="mes", how="outer")
    resumen["ingresos"] = resumen["ingresos"].fillna(0.0)
    resumen["gastos"] = resumen["gastos"].fillna(0.0)
    resumen["balance"] = resumen["ingresos"] - resumen["gastos"]

    meses_totales = pd.Index(sorted(set(datos["mes"].dropna().tolist())))
    if len(meses_totales) == 0:
        return pd.DataFrame(columns=columnas)

    resultado = pd.DataFrame({"mes": meses_totales})
    resultado = resultado.merge(resumen, on="mes", how="left")
    resultado["ingresos"] = resultado["ingresos"].fillna(0.0)
    resultado["gastos"] = resultado["gastos"].fillna(0.0)
    resultado["balance"] = resultado["ingresos"] - resultado["gastos"]
    resultado = resultado[columnas]
    return resultado
