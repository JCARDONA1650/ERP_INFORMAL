import datetime as dt
from io import BytesIO
from zoneinfo import ZoneInfo

from django.contrib.auth import get_user_model
from openpyxl import load_workbook
from rest_framework.test import APITestCase

from accounts.models import AuditLog
from accounts.roles import ADMINISTRADOR, RRHH, SUPERVISOR, assign_role
from attendance.models import Attendance
from payroll.models import PayrollPeriod
from payroll.services import recalculate_period
from projects.models import Project
from workers.models import Employee

TZ = ZoneInfo("America/New_York")
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


class ReportsApiTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.adm = User.objects.create_user("adm", password="x")
        cls.hr = User.objects.create_user("hr", password="x")
        cls.sup = User.objects.create_user("sup", password="x")
        cls.norole = User.objects.create_user("norole", password="x")
        assign_role(cls.adm, ADMINISTRADOR)
        assign_role(cls.hr, RRHH)
        assign_role(cls.sup, SUPERVISOR)
        cls.p1 = Project.objects.create(name="Montego")
        cls.p2 = Project.objects.create(name="Torre Norte")
        cls.p1.supervisors.add(cls.sup)
        cls.ana = Employee.objects.create(full_name="Ana Gomez", hourly_rate="20")
        cls.beto = Employee.objects.create(full_name="Beto Ruiz", hourly_rate="10")
        cls.period = PayrollPeriod.objects.create(
            start_date=dt.date(2026, 11, 2), end_date=dt.date(2026, 11, 8), created_by=cls.adm
        )

    def work(self, project, emp, day=3):
        d = dt.date(2026, 11, day)
        Attendance.objects.create(
            project=project, employee=emp, date=d,
            check_in=dt.datetime(2026, 11, day, 7, tzinfo=TZ), check_out=dt.datetime(2026, 11, day, 15, tzinfo=TZ),
        )

    # ── nómina ──
    def test_nomina_xlsx_y_pdf_para_backoffice(self):
        self.work(self.p1, self.ana)
        recalculate_period(self.period, self.adm)
        for user in (self.adm, self.hr):
            self.client.force_authenticate(user)
            r = self.client.get(f"/api/reports/payroll/{self.period.pk}/xlsx/")
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r["Content-Type"], XLSX)
            self.assertIn('attachment; filename="nomina_20261102_20261108.xlsx"', r["Content-Disposition"])
            self.assertEqual(r["Cache-Control"], "no-store")
            self.assertIn("Ana Gomez", [c.value for row in load_workbook(BytesIO(r.content)).active.iter_rows() for c in row])
            p = self.client.get(f"/api/reports/payroll/{self.period.pk}/pdf/")
            self.assertEqual(p["Content-Type"], "application/pdf")
            self.assertTrue(p.content.startswith(b"%PDF"))

    def test_nomina_sin_permiso(self):
        url = f"/api/reports/payroll/{self.period.pk}/xlsx/"
        self.assertEqual(self.client.get(url).status_code, 401)
        for user in (self.sup, self.norole):
            self.client.force_authenticate(user)
            self.assertEqual(self.client.get(url).status_code, 403)

    def test_formato_invalido_y_periodo_inexistente(self):
        self.client.force_authenticate(self.adm)
        self.assertEqual(self.client.get(f"/api/reports/payroll/{self.period.pk}/docx/").status_code, 400)
        self.assertEqual(self.client.get("/api/reports/payroll/9999/xlsx/").status_code, 404)

    def test_exportar_queda_auditado(self):
        self.client.force_authenticate(self.hr)
        self.client.get(f"/api/reports/payroll/{self.period.pk}/pdf/")
        self.assertTrue(AuditLog.objects.filter(action="exportar", entity="PayrollPeriod").exists())

    # ── asistencia ──
    def test_asistencia_requiere_rango_valido(self):
        self.client.force_authenticate(self.adm)
        base = "/api/reports/attendance/xlsx/"
        self.assertEqual(self.client.get(base).status_code, 400)
        self.assertEqual(self.client.get(base + "?date_from=2026-11-01").status_code, 400)
        self.assertEqual(self.client.get(base + "?date_from=x&date_to=y").status_code, 400)
        self.assertEqual(self.client.get(base + "?date_from=2026-11-10&date_to=2026-11-01").status_code, 400)
        self.assertEqual(self.client.get(base + "?date_from=2020-01-01&date_to=2026-11-01").status_code, 400)
        self.assertEqual(self.client.get(base + "?date_from=2026-11-01&date_to=2026-11-30&project=abc").status_code, 400)

    def test_supervisor_exporta_solo_sus_proyectos(self):
        self.work(self.p1, self.ana)
        self.work(self.p2, self.beto)
        url = "/api/reports/attendance/xlsx/?date_from=2026-11-01&date_to=2026-11-30"
        self.client.force_authenticate(self.sup)
        cells = [c.value for row in load_workbook(BytesIO(self.client.get(url).content)).active.iter_rows() for c in row]
        self.assertIn("Montego", cells)
        self.assertNotIn("Torre Norte", cells)
        self.client.force_authenticate(self.adm)
        cells = [c.value for row in load_workbook(BytesIO(self.client.get(url).content)).active.iter_rows() for c in row]
        self.assertIn("Torre Norte", cells)

    def test_proyecto_con_formula_no_se_ejecuta_en_excel(self):
        evil = Project.objects.create(name="=HYPERLINK(1)")
        self.work(evil, self.beto)
        self.client.force_authenticate(self.adm)
        r = self.client.get("/api/reports/attendance/xlsx/?date_from=2026-11-01&date_to=2026-11-30")
        texts = [c.value for row in load_workbook(BytesIO(r.content)).active.iter_rows() for c in row if isinstance(c.value, str)]
        self.assertIn("'=HYPERLINK(1)", texts)
        self.assertNotIn("=HYPERLINK(1)", texts)

    def test_asistencia_pdf_y_sin_permiso(self):
        self.client.force_authenticate(self.norole)
        self.assertEqual(self.client.get("/api/reports/attendance/pdf/?date_from=2026-11-01&date_to=2026-11-30").status_code, 403)
        self.client.force_authenticate(self.hr)
        r = self.client.get("/api/reports/attendance/pdf/?date_from=2026-11-01&date_to=2026-11-30")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.content.startswith(b"%PDF"))

    # ── finanzas ──
    def test_finanzas_solo_administrador(self):
        url = f"/api/reports/finance/{self.p1.pk}/xlsx/"
        for user in (self.hr, self.sup):
            self.client.force_authenticate(user)
            self.assertEqual(self.client.get(url).status_code, 403)
        self.client.force_authenticate(self.adm)
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.client.get(f"/api/reports/finance/{self.p1.pk}/pdf/").status_code, 200)
        self.assertEqual(self.client.get(url + "?date_from=mal").status_code, 400)
        self.assertEqual(self.client.get("/api/reports/finance/9999/xlsx/").status_code, 404)
