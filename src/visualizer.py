from __future__ import annotations

from typing import Any

import pandas as pd
import plotly.graph_objects as go


COLORES = {
    "fondo": "#F7F8FC",
    "texto": "#1F2937",
    "ingresos": "#2E8B57",
    "gastos": "#D94F4F",
    "balance": "#4F46E5",
    "gris": "#94A3B8",
    "rojo": "#DC2626",
    "azul": "#2563EB",
    "naranja": "#F59E0B",
}


def _normaliza_dataframe(df: Any) -> pd.DataFrame:
    """Convierte un valor a DataFrame o devuelve un DataFrame vacío si no aplica."""
    if isinstance(df, pd.DataFrame):
        return df.copy()
    if isinstance(df, dict):
        return pd.DataFrame(df)
    return pd.DataFrame()


def _es_vacio(valor: Any) -> bool:
    """Determina si el valor es nulo o vacío."""
    if valor is None:
        return True
    if isinstance(valor, pd.DataFrame):
        return valor.empty
    if isinstance(valor, (dict, list, tuple, set)):
        return len(valor) == 0
    return False


def _formatea_mxn(valor: Any) -> str:
    """Formatea un valor numérico en formato monetario MXN."""
    try:
        numero = float(valor)
    except (TypeError, ValueError):
        return "$0.00 MXN"
    return f"${numero:,.2f} MXN"


def figura_vacia(mensaje: str = "Sin datos para mostrar") -> go.Figure:
    """Crea una figura vacía con un mensaje centrado."""
    fig = go.Figure()
    fig.add_annotation(
        text=mensaje,
        x=0.5,
        y=0.5,
        xref="paper",
        yref="paper",
        showarrow=False,
        font={"size": 22, "color": COLORES["texto"]},
        align="center",
    )
    fig.update_layout(
        plot_bgcolor=COLORES["fondo"],
        paper_bgcolor=COLORES["fondo"],
        xaxis={"visible": False},
        yaxis={"visible": False},
        margin={"l": 20, "r": 20, "t": 20, "b": 20},
    )
    return fig


def grafica_ingresos_vs_gastos(balance: dict) -> go.Figure:
    """Genera una gráfica de barras con ingresos, gastos y balance."""
    if _es_vacio(balance):
        return figura_vacia()
    if not isinstance(balance, dict) or not {"ingresos", "gastos", "balance"}.issubset(balance.keys()):
        return figura_vacia("Faltan datos para mostrar el balance")

    ingresos = float(balance.get("ingresos", 0) or 0)
    gastos = float(balance.get("gastos", 0) or 0)
    balance_total = float(balance.get("balance", 0) or 0)

    fig = go.Figure(
        data=[
            go.Bar(
                x=["Ingresos", "Gastos", "Balance"],
                y=[ingresos, gastos, balance_total],
                marker_color=[COLORES["ingresos"], COLORES["gastos"], COLORES["balance"]],
                hovertemplate="%{x}<br>Valor: %{y:$,.2f} MXN<extra></extra>",
            )
        ]
    )
    fig.update_layout(
        title="Ingresos vs. gastos y balance",
        xaxis_title="Concepto",
        yaxis_title="Monto (MXN)",
        template="plotly_white",
        paper_bgcolor=COLORES["fondo"],
        plot_bgcolor=COLORES["fondo"],
        font={"color": COLORES["texto"]},
        bargap=0.35,
        margin={"l": 40, "r": 20, "t": 50, "b": 40},
    )
    fig.update_yaxes(tickprefix="$", tickformat=",.2f")
    return fig


def grafica_tendencia_mensual(df_tendencia) -> go.Figure:
    """Genera una línea de ingresos y gastos por mes."""
    df = _normaliza_dataframe(df_tendencia)
    if df.empty:
        return figura_vacia()

    columnas_requeridas = {"mes", "ingresos", "gastos"}
    if not columnas_requeridas.issubset(df.columns):
        return figura_vacia("Faltan columnas para la tendencia mensual")

    df = df.copy()
    for col in ["ingresos", "gastos"]:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=df["mes"],
            y=df["ingresos"],
            mode="lines+markers",
            name="Ingresos",
            line={"color": COLORES["ingresos"], "width": 3},
            marker={"size": 7},
            hovertemplate="%{x}<br>Ingresos: $%{y:,.2f} MXN<extra></extra>",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=df["mes"],
            y=df["gastos"],
            mode="lines+markers",
            name="Gastos",
            line={"color": COLORES["gastos"], "width": 3},
            marker={"size": 7},
            hovertemplate="%{x}<br>Gastos: $%{y:,.2f} MXN<extra></extra>",
        )
    )
    fig.update_layout(
        title="Tendencia mensual de ingresos y gastos",
        xaxis_title="Mes",
        yaxis_title="Monto (MXN)",
        template="plotly_white",
        paper_bgcolor=COLORES["fondo"],
        plot_bgcolor=COLORES["fondo"],
        font={"color": COLORES["texto"]},
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "xanchor": "left", "x": 0},
        margin={"l": 40, "r": 20, "t": 50, "b": 40},
    )
    fig.update_yaxes(tickprefix="$", tickformat=",.2f")
    return fig


def grafica_real_vs_presupuesto(df_categorias, umbral_desviacion: float = 10.0) -> go.Figure:
    """Compara el gasto real contra el presupuesto y resalta los desvíos relevantes."""
    df = _normaliza_dataframe(df_categorias)
    if df.empty:
        return figura_vacia()

    columnas_requeridas = {"categoria", "presupuesto", "gasto_real", "desviacion_pct"}
    if not columnas_requeridas.issubset(df.columns):
        return figura_vacia("Faltan columnas para comparar real vs presupuesto")

    df = df.copy()
    for col in ["presupuesto", "gasto_real", "desviacion_pct"]:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    colores_barras = [
        COLORES["rojo"] if abs(float(valor)) > abs(float(umbral_desviacion)) else COLORES["azul"]
        for valor in df["desviacion_pct"]
    ]

    fig = go.Figure(
        data=[
            go.Bar(
                x=df["categoria"].astype(str),
                y=df["presupuesto"],
                name="Presupuesto",
                marker={"color": COLORES["azul"]},
                hovertemplate="%{x}<br>Presupuesto: $%{y:,.2f} MXN<extra></extra>",
            ),
            go.Bar(
                x=df["categoria"].astype(str),
                y=df["gasto_real"],
                name="Real",
                marker={"color": colores_barras},
                hovertemplate="%{x}<br>Real: $%{y:,.2f} MXN<extra></extra>",
            ),
        ]
    )
    fig.update_layout(
        title="Gasto real vs. presupuesto por categoría",
        xaxis_title="Categoría",
        yaxis_title="Monto (MXN)",
        template="plotly_white",
        paper_bgcolor=COLORES["fondo"],
        plot_bgcolor=COLORES["fondo"],
        font={"color": COLORES["texto"]},
        barmode="group",
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "xanchor": "left", "x": 0},
        margin={"l": 40, "r": 20, "t": 60, "b": 80},
    )
    fig.update_yaxes(tickprefix="$", tickformat=",.2f")
    return fig


def grafica_distribucion_gasto(df_categorias) -> go.Figure:
    """Genera una dona con la distribución del gasto real por categoría."""
    df = _normaliza_dataframe(df_categorias)
    if df.empty:
        return figura_vacia()

    columnas_requeridas = {"categoria", "gasto_real"}
    if not columnas_requeridas.issubset(df.columns):
        return figura_vacia("Faltan columnas para la distribución de gastos")

    df = df.copy()
    df["gasto_real"] = pd.to_numeric(df["gasto_real"], errors="coerce").fillna(0)
    df = df[df["gasto_real"] > 0]
    if df.empty:
        return figura_vacia("Sin gastos para distribuir")

    palette = [
        COLORES["azul"], COLORES["naranja"], COLORES["ingresos"], COLORES["gastos"],
        COLORES["gris"], COLORES["balance"], COLORES["rojo"],
    ]

    fig = go.Figure(
        data=[
            go.Pie(
                labels=df["categoria"].astype(str),
                values=df["gasto_real"],
                hole=0.45,
                marker={"colors": palette[: len(df)], "line": {"color": "white", "width": 2}},
                hovertemplate="%{label}<br>%{value:$,.2f} MXN<extra></extra>",
            )
        ]
    )
    fig.update_layout(
        title="Distribución del gasto por categoría",
        template="plotly_white",
        paper_bgcolor=COLORES["fondo"],
        plot_bgcolor=COLORES["fondo"],
        font={"color": COLORES["texto"]},
        legend={"title": "Categorías", "orientation": "v"},
        margin={"l": 40, "r": 40, "t": 50, "b": 20},
    )
    return fig
