import datetime as dt
from decimal import Decimal
from io import BytesIO
from zoneinfo import ZoneInfo

from django.contrib.auth import get_user_model
from django.test import TestCase
from openpyxl import load_workbook

from attendance.models import Attendance
from finance.models import ProjectExpense, ProjectIncome
from finance.services import expenses_by_category, project_summary
from payroll.models import PayrollPeriod
from payroll.services import recalculate_period, set_adjustment
from projects.models import Project
from workers.models import Employee

from .exports import Table, attendance_table, finance_table, payroll_table, to_pdf, to_xlsx
from .services import attendance_rows

TZ = ZoneInfo("America/New_York")


class ExportBase(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("adm", password="x")
        self.project = Project.objects.create(name="Montego", contract_value="1000")
        self.ana = Employee.objects.create(full_name="Ana Gomez", hourly_rate="20", document_id="A-1")
        d = dt.date(2026, 11, 3)
        Attendance.objects.create(
            project=self.project, employee=self.ana, date=d,
            check_in=dt.datetime(2026, 11, 3, 7, tzinfo=TZ), check_out=dt.datetime(2026, 11, 3, 15, tzinfo=TZ),
        )
        self.period = PayrollPeriod.objects.create(
            start_date=dt.date(2026, 11, 2), end_date=dt.date(2026, 11, 8), created_by=self.user
        )
        recalculate_period(self.period, self.user)
        set_adjustment(self.period.lines.get(), "-10", "Anticipo", self.user)


class TableContentTests(ExportBase):
    def test_nomina(self):
        t = payroll_table(self.period)
        self.assertEqual(t.rows[0][0], "Ana Gomez")
        self.assertEqual(t.rows[0][2], "07:00")
        self.assertEqual(t.rows[0][7], Decimal("130.00"))
        self.assertEqual(t.totals[0][6], "Total a pagar (USD)")
        self.assertEqual(t.totals[0][7], Decimal("130.00"))
        self.assertEqual(t.filename, "nomina_20261102_20261108")

    def test_asistencia(self):
        rows = attendance_rows(dt.date(2026, 11, 1), dt.date(2026, 11, 30))
        t = attendance_table(rows, dt.date(2026, 11, 1), dt.date(2026, 11, 30))
        self.assertEqual(t.rows[0][2], "Ana Gomez")
        self.assertEqual(t.rows[0][3:6], ["07:00", "15:00", "07:00"])
        self.assertIn("Jornadas: 1", t.context[1])

    def test_finanzas(self):
        ProjectIncome.objects.create(project=self.project, date=dt.date(2026, 11, 2), amount="400", created_by=self.user)
        ProjectExpense.objects.create(project=self.project, date=dt.date(2026, 11, 3), amount="150", category="materials", created_by=self.user)
        t = finance_table(self.project, project_summary(self.project), expenses_by_category(self.project))
        self.assertEqual(t.rows[0], ["USD", Decimal("400.00"), Decimal("150.00"), Decimal("250.00")])
        self.assertEqual(t.rows[1][0], "Gasto · materials")
        self.assertIn("Facturado: 40.0%", t.context[1])


class RenderTests(ExportBase):
    def test_xlsx_se_puede_leer_y_tiene_montos_numericos(self):
        wb = load_workbook(BytesIO(to_xlsx(payroll_table(self.period))))
        ws = wb.active
        values = [[c.value for c in row] for row in ws.iter_rows()]
        flat = [v for row in values for v in row]
        self.assertIn("Ana Gomez", flat)
        self.assertIn(130.0, flat)
        total_cell = next(c for row in ws.iter_rows() for c in row if c.value == 130.0)
        self.assertEqual(total_cell.number_format, "#,##0.00")

    def test_xlsx_neutraliza_formulas(self):
        evil = Table(
            title="X", context=["=HYPERLINK(\"http://malo\")"], headers=["Nombre"],
            rows=[["=1+1"], ["+cmd"], ["-5x"], ["@SUM(A1)"], ["normal"]],
        )
        ws = load_workbook(BytesIO(to_xlsx(evil))).active
        texts = [c.value for row in ws.iter_rows() for c in row if isinstance(c.value, str)]
        self.assertNotIn("=1+1", texts)
        self.assertIn("'=1+1", texts)
        self.assertIn("'+cmd", texts)
        self.assertIn("'@SUM(A1)", texts)
        self.assertIn("normal", texts)
        self.assertTrue(all(not t.startswith("=") for t in texts))

    def test_pdf_valido_y_con_texto_peligroso_escapado(self):
        pdf = to_pdf(payroll_table(self.period))
        self.assertTrue(pdf.startswith(b"%PDF"))
        tricky = Table(title="<b>x</b>", context=["a & b <script>"], headers=["H"], rows=[["<i>&</i>"]])
        self.assertTrue(to_pdf(tricky).startswith(b"%PDF"))  # no revienta con marcado

    def test_pdf_sin_datos(self):
        empty = Table(title="Vacío", context=[], headers=["A", "B"], rows=[])
        self.assertTrue(to_pdf(empty).startswith(b"%PDF"))
        ws = load_workbook(BytesIO(to_xlsx(empty))).active
        self.assertEqual(ws["A1"].value, "Vacío")
