import json
import unittest

import pandas as pd

from src.report_engine import generar_reporte, nombre_archivo, reporte_a_bytes


class GenerarReporteTests(unittest.TestCase):
    def setUp(self):
        self.movimientos = pd.DataFrame(
            [
                {
                    "fecha": "2026-08-01",
                    "tipo": "ingreso",
                    "categoria": "Colegiaturas",
                    "monto": 1000,
                    "monto_presupuestado": None,
                    "responsable": "Laura",
                    "cargo": "Directora",
                    "estado_aprobacion": "aprobado",
                },
                {
                    "fecha": "2026-08-05",
                    "tipo": "gasto",
                    "categoria": "Transporte escolar",
                    "monto": 150,
                    "monto_presupuestado": 100,
                    "responsable": "Jorge",
                    "cargo": "Coordinador",
                    "estado_aprobacion": "aprobado",
                },
                {
                    "fecha": "2026-09-05",
                    "tipo": "gasto",
                    "categoria": "Transporte escolar",
                    "monto": 80,
                    "monto_presupuestado": 100,
                    "responsable": "Jorge",
                    "cargo": "Coordinador",
                    "estado_aprobacion": "pendiente",
                },
            ]
        )

    def test_incluye_resumenes_y_aplica_filtros(self):
        reporte = generar_reporte(
            self.movimientos,
            categoria="transporte escolar",
            fecha_inicio="2026-08-01",
            fecha_fin="2026-08-31",
        )

        self.assertEqual(reporte["categoria"], "Transporte escolar")
        self.assertEqual(reporte["balance"]["total_gastos"], 150.0)
        self.assertEqual(len(reporte["gastos_por_categoria"]), 1)
        self.assertEqual(len(reporte["ineficiencias"]), 1)
        self.assertEqual(reporte["responsables"][0]["monto_total_aprobado"], 150)
        self.assertEqual(reporte["periodo_inicio"], "2026-08-01")
        self.assertEqual(reporte["periodo_fin"], "2026-08-31")

    def test_periodo_sin_datos_conserva_claves_y_mensaje(self):
        reporte = generar_reporte(self.movimientos, fecha_inicio="2027-01-01")

        self.assertEqual(
            set(reporte) - {"mensaje"},
            {
                "titulo",
                "periodo_inicio",
                "periodo_fin",
                "categoria",
                "balance",
                "gastos_por_categoria",
                "ineficiencias",
                "responsables",
                "fecha_generacion",
            },
        )
        self.assertEqual(reporte["mensaje"], "No hay movimientos para los filtros seleccionados.")
        self.assertEqual(reporte["gastos_por_categoria"], [])

    def test_categoria_inexistente_lanza_error(self):
        with self.assertRaises(ValueError):
            generar_reporte(self.movimientos, categoria="Categoría nueva")

    def test_exporta_json_csv_y_nombre_sin_acentos(self):
        reporte = generar_reporte(self.movimientos, categoria="Transporte escolar")

        contenido_json = reporte_a_bytes(reporte, "json")
        self.assertIsInstance(json.loads(contenido_json), dict)
        self.assertIn(b"Transporte escolar", contenido_json)
        self.assertIn(b"seccion,campo,valor", reporte_a_bytes(reporte, "csv"))
        self.assertRegex(nombre_archivo(reporte, "pdf"), r"^true_sunrise_transporte_escolar_\d{4}-\d{2}\.pdf$")

    def test_exporta_pdf(self):
        reporte = generar_reporte(self.movimientos)

        self.assertTrue(reporte_a_bytes(reporte, "pdf").startswith(b"%PDF"))

    def test_formato_invalido_lanza_error(self):
        with self.assertRaises(ValueError):
            reporte_a_bytes({}, "xlsx")


if __name__ == "__main__":
    unittest.main()