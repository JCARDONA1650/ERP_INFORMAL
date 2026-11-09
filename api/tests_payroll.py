import datetime as dt
from decimal import Decimal
from zoneinfo import ZoneInfo

from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from accounts.models import AuditLog
from accounts.roles import ADMINISTRADOR, RRHH, SUPERVISOR, assign_role
from attendance.models import Attendance
from payroll.models import PayrollLine, PayrollPeriod
from projects.models import Project
from workers.models import Employee

TZ = ZoneInfo("America/New_York")
URL = "/api/payroll/periods/"


class PayrollApiTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.adm = User.objects.create_user("adm", password="x")
        cls.hr = User.objects.create_user("hr", password="x")
        cls.sup = User.objects.create_user("sup", password="x")
        assign_role(cls.adm, ADMINISTRADOR)
        assign_role(cls.hr, RRHH)
        assign_role(cls.sup, SUPERVISOR)
        cls.project = Project.objects.create(name="Montego")
        cls.ana = Employee.objects.create(full_name="Ana Gomez", hourly_rate="20")
        cls.beto = Employee.objects.create(full_name="Beto Ruiz", hourly_rate="10", currency="COP")

    def work(self, emp, day):
        d = dt.date(2026, 11, day)
        Attendance.objects.create(
            project=self.project, employee=emp, date=d,
            check_in=dt.datetime(d.year, d.month, d.day, 7, tzinfo=TZ),
            check_out=dt.datetime(d.year, d.month, d.day, 15, tzinfo=TZ),
        )

    def create_period(self, user=None, **kw):
        self.client.force_authenticate(user or self.hr)
        data = {"start_date": "2026-11-02", "end_date": "2026-11-08", **kw}
        return self.client.post(URL, data, format="json")

    # ── acceso ──
    def test_supervisor_y_anonimo_no_acceden(self):
        self.assertEqual(self.client.get(URL).status_code, 401)
        self.client.force_authenticate(self.sup)
        self.assertEqual(self.client.get(URL).status_code, 403)
        self.assertEqual(self.client.post(URL, {}, format="json").status_code, 403)

    # ── crear ──
    def test_crear_periodo(self):
        r = self.create_period()
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data["status"], "OPEN")
        self.assertEqual(PayrollPeriod.objects.get().created_by, self.hr)

    def test_fechas_invertidas_y_duplicado_son_400(self):
        self.assertEqual(self.create_period(end_date="2026-11-01").status_code, 400)
        self.assertEqual(self.create_period().status_code, 201)
        self.assertEqual(self.create_period().status_code, 400)  # mismo rango, todos los proyectos

    def test_no_se_puede_forzar_el_estado_al_crear(self):
        r = self.create_period(status="CLOSED")
        self.assertEqual(r.data["status"], "OPEN")

    def test_no_hay_delete_ni_put(self):
        pid = self.create_period().data["id"]
        self.assertEqual(self.client.delete(f"{URL}{pid}/").status_code, 405)
        self.assertEqual(self.client.put(f"{URL}{pid}/", {}, format="json").status_code, 405)

    # ── recalcular ──
    def test_recalcular_y_totales_por_moneda(self):
        self.work(self.ana, 3)   # 7 h * 20 = 140 USD
        self.work(self.beto, 3)  # 7 h * 10 = 70 COP
        pid = self.create_period().data["id"]
        r = self.client.post(f"{URL}{pid}/recalculate/")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(len(r.data["lines"]), 2)
        self.assertEqual(r.data["totals"], {"USD": "140.00", "COP": "70.00"})
        line = next(l for l in r.data["lines"] if l["employee"]["full_name"] == "Ana Gomez")
        self.assertEqual(line["hours"], "07:00")
        self.assertEqual(Decimal(line["total"]), Decimal("140.00"))

    def test_detalle_sin_n_mas_1(self):
        for i in range(8):
            e = Employee.objects.create(full_name=f"Persona {chr(65 + i)}", hourly_rate="10")
            self.work(e, 3)
        pid = self.create_period().data["id"]
        self.client.post(f"{URL}{pid}/recalculate/")
        with self.assertNumQueries(4):  # rol + periodo + lineas + trabajadores (prefetch); constante
            self.client.get(f"{URL}{pid}/")

    # ── ajustes ──
    def test_ajustar_linea_con_motivo(self):
        self.work(self.ana, 3)
        pid = self.create_period().data["id"]
        line_id = self.client.post(f"{URL}{pid}/recalculate/").data["lines"][0]["id"]
        r = self.client.post(f"/api/payroll/lines/{line_id}/adjust/", {"amount": "-10", "reason": "Anticipo"}, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(Decimal(r.data["total"]), Decimal("130.00"))
        self.assertTrue(AuditLog.objects.filter(action="ajuste").exists())

    def test_ajuste_sin_motivo_es_400(self):
        self.work(self.ana, 3)
        pid = self.create_period().data["id"]
        line_id = self.client.post(f"{URL}{pid}/recalculate/").data["lines"][0]["id"]
        r = self.client.post(f"/api/payroll/lines/{line_id}/adjust/", {"amount": "5", "reason": ""}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_supervisor_no_ajusta(self):
        self.work(self.ana, 3)
        pid = self.create_period().data["id"]
        line_id = self.client.post(f"{URL}{pid}/recalculate/").data["lines"][0]["id"]
        self.client.force_authenticate(self.sup)
        r = self.client.post(f"/api/payroll/lines/{line_id}/adjust/", {"amount": "5", "reason": "x"}, format="json")
        self.assertEqual(r.status_code, 403)

    # ── cierre ──
    def test_rrhh_no_cierra_pero_admin_si(self):
        self.work(self.ana, 3)
        pid = self.create_period().data["id"]  # autenticado como RRHH
        self.assertEqual(self.client.post(f"{URL}{pid}/close/").status_code, 403)
        self.assertTrue(PayrollPeriod.objects.get(pk=pid).is_open)
        self.client.force_authenticate(self.adm)
        r = self.client.post(f"{URL}{pid}/close/")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data["status"], "CLOSED")
        self.assertEqual(r.data["closed_by"], "adm")
        self.assertTrue(AuditLog.objects.filter(action="cerrar").exists())

    def test_periodo_cerrado_es_inmutable_409(self):
        self.work(self.ana, 3)
        pid = self.create_period().data["id"]
        line_id = self.client.post(f"{URL}{pid}/recalculate/").data["lines"][0]["id"]
        self.client.force_authenticate(self.adm)
        self.client.post(f"{URL}{pid}/close/")
        self.assertEqual(self.client.post(f"{URL}{pid}/recalculate/").status_code, 409)
        self.assertEqual(self.client.post(f"{URL}{pid}/close/").status_code, 409)
        r = self.client.post(f"/api/payroll/lines/{line_id}/adjust/", {"amount": "5", "reason": "x"}, format="json")
        self.assertEqual(r.status_code, 409)
        self.assertEqual(PayrollLine.objects.get(pk=line_id).adjustment, Decimal("0.00"))

    # ── filtros ──
    def test_filtro_por_estado(self):
        a = self.create_period().data["id"]
        self.create_period(start_date="2026-11-09", end_date="2026-11-15")
        self.client.force_authenticate(self.adm)
        self.client.post(f"{URL}{a}/close/")
        self.assertEqual(self.client.get(URL + "?status=CLOSED").data["count"], 1)
        self.assertEqual(self.client.get(URL + "?status=OPEN").data["count"], 1)
        self.assertEqual(self.client.get(URL + "?project=abc").data["count"], 0)
