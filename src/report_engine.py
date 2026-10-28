"""Generación y exportación de informes de transparencia financiera."""

from __future__ import annotations

import csv
import io
import json
import re
import unicodedata
from datetime import date, datetime
from typing import Any

import pandas as pd

from src.tracker import (
    calcular_balance_general,
    detectar_ineficiencias,
    gastos_por_categoria as calcular_gastos_por_categoria,
    obtener_responsables,
)


def _valor_json(valor: Any) -> Any:
    """Convierte valores de pandas y fechas en valores serializables."""
    if isinstance(valor, dict):
        return {str(clave): _valor_json(elemento) for clave, elemento in valor.items()}
    if isinstance(valor, (list, tuple)):
        return [_valor_json(elemento) for elemento in valor]
    if valor is None or valor is pd.NA:
        return None
    if isinstance(valor, (pd.Timestamp, datetime, date)):
        return None if pd.isna(valor) else valor.isoformat()
    if hasattr(valor, "item"):
        valor = valor.item()
    if pd.isna(valor):
        return None
    return valor


def _registros_json(datos: pd.DataFrame) -> list[dict[str, Any]]:
    """Convierte un DataFrame a registros sin valores NaN."""
    return [
        {str(clave): _valor_json(valor) for clave, valor in fila.items()}
        for fila in datos.to_dict(orient="records")
    ]


def _fecha_iso(valor: Any) -> str | None:
    """Devuelve una fecha en formato ISO o None si no se especificó."""
    if valor is None:
        return None
    return pd.Timestamp(valor).date().isoformat()


def generar_reporte(
    df: pd.DataFrame,
    categoria: str | None = None,
    fecha_inicio: Any = None,
    fecha_fin: Any = None,
) -> dict[str, Any]:
    """Genera un informe financiero para una categoría y periodo.

    Args:
        df: DataFrame de movimientos financieros.
        categoria: Categoría opcional que se incluirá en el informe.
        fecha_inicio: Fecha inicial inclusiva del periodo.
        fecha_fin: Fecha final inclusiva del periodo.

    Returns:
        Diccionario con balance, gastos por categoría, ineficiencias,
        responsables y metadatos de generación.

    Raises:
        ValueError: Si el periodo es inválido o la categoría no existe.
    """
    inicio = pd.Timestamp(fecha_inicio).normalize() if fecha_inicio is not None else None
    fin = pd.Timestamp(fecha_fin).normalize() if fecha_fin is not None else None
    if inicio is not None and fin is not None and inicio > fin:
        raise ValueError("La fecha de inicio no puede ser posterior a la fecha de fin.")

    datos = df.copy()
    categoria_informe = categoria
    if categoria is not None:
        if "categoria" not in datos.columns:
            raise ValueError(f"La categoría '{categoria}' no existe.")
        categorias = datos["categoria"].dropna().astype(str)
        coincidencias = categorias[categorias.str.casefold() == categoria.strip().casefold()]
        if coincidencias.empty:
            raise ValueError(f"La categoría '{categoria}' no existe.")
        categoria_informe = str(coincidencias.iloc[0])
        datos = datos.loc[
            datos["categoria"].astype(str).str.casefold()
            == categoria_informe.casefold()
        ].copy()

    if inicio is not None or fin is not None:
        if "fecha" not in datos.columns:
            raise ValueError("No se puede filtrar por periodo: falta la columna 'fecha'.")
        fechas = pd.to_datetime(datos["fecha"], errors="coerce")
        if inicio is not None:
            datos = datos.loc[fechas >= inicio].copy()
            fechas = fechas.loc[datos.index]
        if fin is not None:
            datos = datos.loc[fechas < fin + pd.Timedelta(days=1)].copy()

    balance = calcular_balance_general(datos)
    if datos.empty:
        periodo_inicio = _fecha_iso(fecha_inicio)
        periodo_fin = _fecha_iso(fecha_fin)
        gastos: list[dict[str, Any]] = []
        ineficiencias: list[dict[str, Any]] = []
        responsables: list[dict[str, Any]] = []
        mensaje = "No hay movimientos para los filtros seleccionados."
    else:
        fechas_validas = (
            pd.to_datetime(datos["fecha"], errors="coerce").dropna()
            if "fecha" in datos.columns
            else pd.Series(dtype="datetime64[ns]")
        )
        periodo_inicio = (
            inicio.date().isoformat()
            if inicio is not None
            else (fechas_validas.min().date().isoformat() if not fechas_validas.empty else None)
        )
        periodo_fin = (
            fin.date().isoformat()
            if fin is not None
            else (fechas_validas.max().date().isoformat() if not fechas_validas.empty else None)
        )

        gastos_df = calcular_gastos_por_categoria(datos)
        gastos = _registros_json(gastos_df)

        gastos_movimientos = (
            datos.loc[datos["tipo"].astype(str).str.casefold() == "gasto"].copy()
            if "tipo" in datos.columns
            else datos.iloc[0:0].copy()
        )
        ineficiencias = _registros_json(detectar_ineficiencias(gastos_movimientos))

        datos_responsables = datos.rename(
            columns={"estado_aprobacion": "estado"}
        )
        responsables = _registros_json(
            obtener_responsables(datos_responsables, categoria=categoria_informe)
        )
        mensaje = None

    titulo = "Informe de transparencia financiera"
    if categoria_informe is not None:
        titulo += f" - {categoria_informe}"

    reporte: dict[str, Any] = {
        "titulo": titulo,
        "periodo_inicio": periodo_inicio,
        "periodo_fin": periodo_fin,
        "categoria": categoria_informe,
        "balance": _valor_json(balance),
        "gastos_por_categoria": gastos,
        "ineficiencias": ineficiencias,
        "responsables": responsables,
        "fecha_generacion": datetime.now().astimezone().isoformat(),
    }
    if mensaje is not None:
        reporte["mensaje"] = mensaje
    return reporte


def _csv_bytes(reporte: dict[str, Any]) -> bytes:
    """Exporta cada sección del informe como filas CSV."""
    salida = io.StringIO(newline="")
    escritor = csv.writer(salida)
    escritor.writerow(["seccion", "campo", "valor"])
    for clave, valor in reporte.items():
        if isinstance(valor, dict):
            for campo, dato in valor.items():
                escritor.writerow([clave, campo, json.dumps(_valor_json(dato), ensure_ascii=False)])
        elif isinstance(valor, list):
            for indice, dato in enumerate(valor, start=1):
                escritor.writerow(
                    [clave, indice, json.dumps(_valor_json(dato), ensure_ascii=False)]
                )
        else:
            escritor.writerow([clave, "", _valor_json(valor)])
    return salida.getvalue().encode("utf-8")


def _pdf_bytes(reporte: dict[str, Any]) -> bytes:
    """Genera un PDF con las secciones principales del informe."""
    try:
        from fpdf import FPDF
    except ImportError as error:
        raise ImportError(
            "La exportación a PDF requiere fpdf2. Instálalo con "
            "'pip install fpdf2'."
        ) from error

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.multi_cell(0, 10, "True Sunrise, Informe de Transparencia", new_x="LMARGIN")
    pdf.set_font("Helvetica", size=10)
    pdf.multi_cell(
        0, 7, str(reporte.get("titulo", "Informe financiero")), new_x="LMARGIN"
    )
    pdf.multi_cell(
        0,
        7,
        f"Periodo: {reporte.get('periodo_inicio') or 'Sin inicio'} - "
        f"{reporte.get('periodo_fin') or 'Sin fin'}",
        new_x="LMARGIN",
    )
    if reporte.get("categoria"):
        pdf.multi_cell(0, 7, f"Categoría: {reporte['categoria']}", new_x="LMARGIN")
    pdf.ln(3)

    def agregar_tabla(
        encabezado: str,
        columnas: list[str],
        filas: list[list[str]],
    ) -> None:
        pdf.set_font("Helvetica", "B", 12)
        pdf.multi_cell(0, 8, encabezado, new_x="LMARGIN")
        pdf.set_font("Helvetica", "B", 8)
        ancho = pdf.epw / len(columnas)
        for columna in columnas:
            pdf.cell(ancho, 7, columna[:24], border=1)
        pdf.ln()
        pdf.set_font("Helvetica", size=8)
        for fila in filas:
            for valor in fila:
                pdf.cell(ancho, 7, valor[:30], border=1)
            pdf.ln()
        if not filas:
            pdf.cell(pdf.epw, 7, "Sin datos", border=1)
            pdf.ln()
        pdf.ln(3)

    balance = reporte.get("balance") or {}
    agregar_tabla(
        "Balance",
        ["Concepto", "Monto"],
        [
            [str(clave), f"${float(valor or 0):,.2f} MXN"]
            for clave, valor in balance.items()
            if clave != "porcentaje_gastado"
        ],
    )

    gastos = reporte.get("gastos_por_categoria", [])
    agregar_tabla(
        "Gastos por categoría",
        ["Categoría", "Gasto", "Presupuesto", "Desviación"],
        [
            [
                str(fila.get("categoria", "")),
                f"${float(fila.get('gasto_real') or 0):,.2f} MXN",
                (
                    f"${float(fila['presupuestado']):,.2f} MXN"
                    if fila.get("presupuestado") is not None
                    else "Sin presupuesto"
                ),
                (
                    f"${float(fila['desviacion']):,.2f} MXN"
                    if fila.get("desviacion") is not None
                    else "N/D"
                ),
            ]
            for fila in gastos
        ],
    )

    ineficiencias = reporte.get("ineficiencias", [])
    agregar_tabla(
        "Ineficiencias",
        ["Categoría", "Monto", "Responsable", "Motivo"],
        [
            [
                str(fila.get("categoria", "")),
                f"${float(fila.get('monto') or 0):,.2f} MXN",
                str(fila.get("responsable") or "Sin responsable"),
                str(fila.get("motivo", "")),
            ]
            for fila in ineficiencias
        ],
    )

    responsables = reporte.get("responsables", [])
    agregar_tabla(
        "Responsables",
        ["Responsable", "Cargo", "Movimientos", "Monto aprobado"],
        [
            [
                str(fila.get("responsable") or "Sin responsable"),
                str(fila.get("cargo") or ""),
                str(fila.get("movimientos_aprobados", 0)),
                f"${float(fila.get('monto_total_aprobado') or 0):,.2f} MXN",
            ]
            for fila in responsables
        ],
    )
    return bytes(pdf.output())


def reporte_a_bytes(reporte: dict[str, Any], formato: str = "pdf") -> bytes:
    """Exporta un informe como PDF, CSV o JSON.

    Args:
        reporte: Diccionario producido por :func:`generar_reporte`.
        formato: Formato de salida: ``pdf``, ``csv`` o ``json``.

    Returns:
        Contenido del archivo en bytes.

    Raises:
        ValueError: Si el formato solicitado no está soportado.
        ImportError: Si se solicita PDF y fpdf2 no está instalado.
    """
    formato_normalizado = formato.strip().lower()
    if formato_normalizado == "json":
        return json.dumps(
            _valor_json(reporte), ensure_ascii=False, indent=2
        ).encode("utf-8")
    if formato_normalizado == "csv":
        return _csv_bytes(reporte)
    if formato_normalizado == "pdf":
        return _pdf_bytes(reporte)
    raise ValueError("Formato inválido. Usa 'pdf', 'csv' o 'json'.")


def nombre_archivo(reporte: dict[str, Any], formato: str) -> str:
    """Crea un nombre de archivo limpio para descargar el informe."""
    extension = formato.strip().lower()
    if extension not in {"pdf", "csv", "json"}:
        raise ValueError("Formato inválido. Usa 'pdf', 'csv' o 'json'.")

    categoria = str(reporte.get("categoria") or "general")
    categoria = unicodedata.normalize("NFKD", categoria)
    categoria = "".join(caracter for caracter in categoria if not unicodedata.combining(caracter))
    categoria = re.sub(r"[^a-zA-Z0-9]+", "_", categoria.lower()).strip("_") or "general"
    fecha = reporte.get("fecha_generacion")
    if fecha:
        fecha_mes = pd.Timestamp(fecha).strftime("%Y-%m")
    else:
        fecha_mes = datetime.now().strftime("%Y-%m")
    return f"true_sunrise_{categoria}_{fecha_mes}.{extension}"
