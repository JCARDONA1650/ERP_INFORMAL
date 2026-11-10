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

    # ── Finanzas: el cierre registra el gasto y reabrir lo elimina ──
    def work_at(self, emp, day, project, hours=8):
        d = dt.date(2026, 11, day)
        Attendance.objects.create(
            project=project, employee=emp, date=d,
            check_in=dt.datetime(d.year, d.month, d.day, 7, tzinfo=TZ),
            check_out=dt.datetime(d.year, d.month, d.day, 7 + hours, tzinfo=TZ),
        )

    def close(self, pid):
        self.client.force_authenticate(self.adm)
        self.client.post(f"{URL}{pid}/recalculate/")
        return self.client.post(f"{URL}{pid}/close/")

    def test_cerrar_registra_un_gasto_de_nomina_por_proyecto_repartido_por_asistencia(self):
        from finance.models import ProjectExpense

        other = Project.objects.create(name="Otra obra")
        self.work_at(self.ana, 3, self.project, 8)   # 7 h netas (almuerzo) * 20 = 140
        self.work_at(self.ana, 4, other, 8)          # 140 en la otra obra
        self.work_at(self.beto, 3, self.project, 8)  # 70 COP
        pid = self.create_period().data["id"]
        self.assertEqual(self.close(pid).status_code, 200)
        expenses = ProjectExpense.objects.filter(payroll_period_id=pid)
        got = {(e.project_id, e.currency): e.amount for e in expenses}
        self.assertEqual(got, {
            (self.project.pk, "USD"): Decimal("140.00"),
            (other.pk, "USD"): Decimal("140.00"),
            (self.project.pk, "COP"): Decimal("70.00"),
        })
        first = expenses.first()
        self.assertEqual(first.category, "payroll")
        self.assertEqual(first.date, dt.date(2026, 11, 8))
        self.assertEqual(first.created_by, self.adm)

    def test_el_total_de_gastos_coincide_con_el_total_de_la_nomina_con_ajustes(self):
        from django.db.models import Sum

        from finance.models import ProjectExpense

        other = Project.objects.create(name="Otra obra")
        self.work_at(self.ana, 3, self.project, 3)   # menos horas
        self.work_at(self.ana, 4, other, 8)          # donde más trabajó: recibe el ajuste
        pid = self.create_period().data["id"]
        self.client.force_authenticate(self.adm)
        line_id = self.client.post(f"{URL}{pid}/recalculate/").data["lines"][0]["id"]
        self.client.post(f"/api/payroll/lines/{line_id}/adjust/", {"amount": "-10", "reason": "Anticipo"}, format="json")
        r = self.client.post(f"{URL}{pid}/close/")
        self.assertEqual(r.status_code, 200, r.data)
        total = ProjectExpense.objects.filter(payroll_period_id=pid).aggregate(t=Sum("amount"))["t"]
        self.assertEqual(total, Decimal(r.data["totals"]["USD"]))
        self.assertEqual(ProjectExpense.objects.get(payroll_period_id=pid, project=other).amount, Decimal("130.00"))

    def test_reabrir_elimina_los_gastos_y_cerrar_de_nuevo_los_recrea_sin_duplicar(self):
        from finance.models import ProjectExpense

        self.work(self.ana, 3)
        pid = self.create_period().data["id"]
        self.close(pid)
        self.assertEqual(ProjectExpense.objects.count(), 1)
        r = self.client.post(f"{URL}{pid}/reopen/")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data["status"], "OPEN")
        self.assertIsNone(r.data["closed_by"])
        self.assertEqual(ProjectExpense.objects.count(), 0)
        self.assertTrue(AuditLog.objects.filter(action="reabrir").exists())
        self.assertEqual(self.client.post(f"{URL}{pid}/recalculate/").status_code, 200)  # vuelve a ser editable
        self.client.post(f"{URL}{pid}/close/")
        self.assertEqual(ProjectExpense.objects.count(), 1)

    def test_solo_el_administrador_reabre_y_solo_si_esta_cerrado(self):
        self.work(self.ana, 3)
        pid = self.create_period().data["id"]
        self.client.force_authenticate(self.adm)
        self.assertEqual(self.client.post(f"{URL}{pid}/reopen/").status_code, 409)  # ya abierto
        self.close(pid)
        self.client.force_authenticate(self.hr)
        self.assertEqual(self.client.post(f"{URL}{pid}/reopen/").status_code, 403)
        self.assertEqual(PayrollPeriod.objects.get(pk=pid).status, "CLOSED")

    def test_el_gasto_generado_por_nomina_no_se_edita_a_mano(self):
        from finance.models import ProjectExpense

        self.work(self.ana, 3)
        pid = self.create_period().data["id"]
        self.close(pid)
        expense = ProjectExpense.objects.get(payroll_period_id=pid)
        r = self.client.patch(f"/api/finance/expenses/{expense.pk}/", {"amount": "1.00"}, format="json")
        self.assertEqual(r.status_code, 400)
        expense.refresh_from_db()
        self.assertEqual(expense.amount, Decimal("140.00"))
        self.assertEqual(self.client.get(f"/api/finance/expenses/{expense.pk}/").data["payroll_period"], pid)

    def test_cierre_con_trabajador_sin_proyecto_para_cargar_es_409_y_no_deja_nada(self):
        from finance.models import ProjectExpense

        pid = self.create_period().data["id"]
        period = PayrollPeriod.objects.get(pk=pid)
        PayrollLine.objects.create(
            period=period, employee=self.ana, hourly_rate="20", currency="USD",
            base_amount="0.00", adjustment="50.00", notes="Bono",
        )
        self.client.force_authenticate(self.adm)
        r = self.client.post(f"{URL}{pid}/close/")
        self.assertEqual(r.status_code, 409)
        self.assertTrue(PayrollPeriod.objects.get(pk=pid).is_open)
        self.assertEqual(ProjectExpense.objects.count(), 0)

    # ── filtros ──
    def test_filtro_por_estado(self):
        a = self.create_period().data["id"]
        self.create_period(start_date="2026-11-09", end_date="2026-11-15")
        self.client.force_authenticate(self.adm)
        self.client.post(f"{URL}{a}/close/")
        self.assertEqual(self.client.get(URL + "?status=CLOSED").data["count"], 1)
        self.assertEqual(self.client.get(URL + "?status=OPEN").data["count"], 1)
        self.assertEqual(self.client.get(URL + "?project=abc").data["count"], 0)
