"""Exportación de reportes a Excel y PDF.

Cada reporte se describe como una `Table` (título, líneas de contexto, encabezados, filas,
totales) y se renderiza con `to_xlsx` / `to_pdf`. Así el contenido se prueba sin depender
del formato de archivo.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from io import BytesIO
from xml.sax.saxutils import escape

from django.utils import timezone
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table as PdfTable, TableStyle

from finance.models import ProjectExpense, ProjectIncome
from payroll.models import PayrollPeriod

from .services import attendance_totals, payroll_rows, payroll_totals

MONEY_FORMAT = "#,##0.00"
_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


@dataclass
class Table:
    title: str
    context: list[str]
    headers: list[str]
    rows: list[list]
    money_cols: set[int] = field(default_factory=set)
    totals: list[list] = field(default_factory=list)
    filename: str = "reporte"


def _safe_text(value):
    """Neutraliza inyección de fórmulas: un texto que empieza con = + - @ se guarda como texto."""
    if isinstance(value, str) and value.startswith(_FORMULA_PREFIXES):
        return "'" + value
    return value


def _hhmm(minutes: int) -> str:
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def _local(dt) -> str:
    return timezone.localtime(dt).strftime("%H:%M") if dt else "—"


def _zone(value) -> str:
    return "Sin ubicación" if value is None else ("Dentro" if value else "Fuera")


# ───────────────────────── Constructores de contenido ─────────────────────────

def payroll_table(period: PayrollPeriod) -> Table:
    rows = payroll_rows(period)
    scope = period.project.name if period.project_id else "Todos los proyectos"
    totals = [
        ["", "", "", "", "", "", f"Total a pagar ({cur})", amount, cur, ""]
        for cur, amount in sorted(payroll_totals(rows).items())
    ]
    return Table(
        title="Nómina",
        context=[
            f"Periodo: {period.start_date:%d/%m/%Y} a {period.end_date:%d/%m/%Y}",
            f"Proyecto: {scope}",
            f"Estado: {'Cerrado' if not period.is_open else 'Abierto'}",
        ],
        headers=["Trabajador", "Documento", "Horas", "Días", "Tarifa/h", "Base", "Ajuste", "Total", "Moneda", "Motivo del ajuste"],
        rows=[
            [r["employee"], r["document_id"] or "", r["hours"], r["days"], r["hourly_rate"],
             r["base_amount"], r["adjustment"], r["total"], r["currency"], r["notes"]]
            for r in rows
        ],
        money_cols={4, 5, 6, 7},
        totals=totals,
        filename=f"nomina_{period.start_date:%Y%m%d}_{period.end_date:%Y%m%d}",
    )


def attendance_table(rows: list[dict], date_from, date_to) -> Table:
    totals = attendance_totals(rows)
    return Table(
        title="Asistencia",
        context=[
            f"Rango: {date_from:%d/%m/%Y} a {date_to:%d/%m/%Y}",
            f"Jornadas: {len(rows)} · Horas netas totales: {_hhmm(totals['total_minutes'])} · "
            f"Pendientes de revisión: {totals['pending_review']}",
        ],
        headers=["Fecha", "Proyecto", "Trabajador", "Ingreso", "Salida", "Horas netas", "Ubicación", "Revisión", "Ajuste manual"],
        rows=[
            [r["date"].strftime("%d/%m/%Y"), r["project"], r["employee"], _local(r["check_in"]),
             _local(r["check_out"]), _hhmm(r["minutes"]), _zone(r["in_zone"]),
             "Pendiente" if r["needs_review"] else "OK", "Sí" if r["manual"] else ""]
            for r in rows
        ],
        filename=f"asistencia_{date_from:%Y%m%d}_{date_to:%Y%m%d}",
    )


def finance_table(project, summary: dict, by_category: dict, date_from=None, date_to=None) -> Table:
    ctx = [f"Proyecto: {project.name}"]
    if date_from or date_to:
        ctx.append(f"Rango: {date_from or '…'} a {date_to or '…'}")
    contract = f"{summary['contract_value']} {summary['contract_currency']}"
    ctx.append(
        f"Contrato: {contract}"
        + (f" · Facturado: {summary['billed_pct']}%" if summary["billed_pct"] is not None else "")
    )
    currencies = sorted(set(summary["incomes"]) | set(summary["expenses"]))
    rows: list[list] = [
        [cur, summary["incomes"].get(cur, Decimal("0.00")), summary["expenses"].get(cur, Decimal("0.00")),
         summary["balance"].get(cur, Decimal("0.00"))]
        for cur in currencies
    ]
    for (cat, cur), total in sorted(by_category.items()):
        rows.append([f"Gasto · {cat}", "", total, ""])
    return Table(
        title="Resumen financiero",
        context=ctx,
        headers=["Moneda / concepto", "Ingresos", "Gastos", "Balance"],
        rows=rows,
        money_cols={1, 2, 3},
        filename=f"finanzas_{project.slug}",
    )


MAX_LEDGER_ROWS = 10000


class LedgerTooLarge(Exception):
    """El registro supera el máximo exportable; hay que acotar el rango."""


def finance_ledger_table(project=None, date_from=None, date_to=None) -> Table:
    """Registro global de movimientos (ingresos y gastos) de todos los proyectos o de uno,
    ordenado por fecha, con totales por moneda (sin conversión)."""
    categories = dict(ProjectExpense.CATEGORY)
    entries = []
    for kind, model in (("Ingreso", ProjectIncome), ("Gasto", ProjectExpense)):
        qs = model.objects.select_related("project", "created_by")
        if project is not None:
            qs = qs.filter(project=project)
        if date_from:
            qs = qs.filter(date__gte=date_from)
        if date_to:
            qs = qs.filter(date__lte=date_to)
        for m in qs.order_by("date", "id")[: MAX_LEDGER_ROWS + 1]:
            category = categories.get(getattr(m, "category", ""), "") if kind == "Gasto" else ""
            entries.append((m.date, m.pk, [
                m.date.isoformat(), m.project.name, kind, category, m.description,
                m.currency, m.amount, m.created_by.get_username(),
            ]))
    if len(entries) > MAX_LEDGER_ROWS:
        raise LedgerTooLarge(f"El registro supera {MAX_LEDGER_ROWS} movimientos; acota el rango de fechas.")
    entries.sort(key=lambda e: (e[0], e[1]))

    totals: dict[str, dict[str, Decimal]] = {}
    for _, _, row in entries:
        bucket = totals.setdefault(row[5], {"Ingreso": Decimal("0.00"), "Gasto": Decimal("0.00")})
        bucket[row[2]] += row[6]
    total_rows = []
    for cur in sorted(totals):
        inc, exp = totals[cur]["Ingreso"], totals[cur]["Gasto"]
        total_rows += [
            ["", "", "Total ingresos", "", "", cur, inc, ""],
            ["", "", "Total gastos", "", "", cur, exp, ""],
            ["", "", "Balance", "", "", cur, inc - exp, ""],
        ]

    ctx = [f"Proyecto: {project.name}" if project is not None else "Proyectos: todos"]
    if date_from or date_to:
        ctx.append(f"Rango: {date_from or '…'} a {date_to or '…'}")
    return Table(
        title="Registro financiero",
        context=ctx,
        headers=["Fecha", "Proyecto", "Tipo", "Categoría", "Descripción", "Moneda", "Monto", "Registró"],
        rows=[row for _, _, row in entries],
        money_cols={6},
        totals=total_rows,
        filename="finanzas_global" if project is None else f"finanzas_registro_{project.slug}",
    )


# ───────────────────────────── Renderizadores ─────────────────────────────

def to_xlsx(table: Table) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = table.title[:31]

    ws.append([table.title])
    ws["A1"].font = Font(bold=True, size=14)
    for line in table.context:
        ws.append([_safe_text(line)])
    ws.append([])

    header_row = ws.max_row + 1
    ws.append(table.headers)
    for cell in ws[header_row]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="13181F")
        cell.alignment = Alignment(horizontal="center")

    def put(row):
        ws.append([
            float(v) if isinstance(v, Decimal) else _safe_text(v) for v in row
        ])
        for i in table.money_cols:
            cell = ws.cell(row=ws.max_row, column=i + 1)
            if isinstance(cell.value, float):
                cell.number_format = MONEY_FORMAT

    for row in table.rows:
        put(row)
    for row in table.totals:
        put(row)
        for cell in ws[ws.max_row]:
            cell.font = Font(bold=True)

    for idx, header in enumerate(table.headers, start=1):
        longest = max([len(str(header))] + [len(str(r[idx - 1])) for r in table.rows if idx - 1 < len(r)])
        ws.column_dimensions[get_column_letter(idx)].width = min(max(longest + 2, 10), 40)
    ws.freeze_panes = ws.cell(row=header_row + 1, column=1)

    out = BytesIO()
    wb.save(out)
    return out.getvalue()


def _fmt(value, money: bool) -> str:
    if isinstance(value, Decimal):
        return f"{value:,.2f}"
    return "" if value is None else str(value)


def to_pdf(table: Table) -> bytes:
    styles = getSampleStyleSheet()
    cell_style = styles["BodyText"]
    cell_style.fontSize = 7.5
    cell_style.leading = 9

    out = BytesIO()
    doc = SimpleDocTemplate(
        out, pagesize=landscape(A4), leftMargin=1.2 * cm, rightMargin=1.2 * cm,
        topMargin=1.2 * cm, bottomMargin=1.2 * cm, title=table.title,
    )
    story = [Paragraph(escape(table.title), styles["Title"])]
    story += [Paragraph(escape(line), styles["Normal"]) for line in table.context]
    story.append(Spacer(1, 0.4 * cm))

    def cells(row):
        return [Paragraph(escape(_fmt(v, i in table.money_cols)), cell_style) for i, v in enumerate(row)]

    data = [[Paragraph(f"<b>{escape(h)}</b>", cell_style) for h in table.headers]]
    data += [cells(r) for r in table.rows] + [cells(r) for r in table.totals]
    if len(data) == 1:
        data.append([Paragraph("Sin datos para el rango seleccionado.", cell_style)] + [""] * (len(table.headers) - 1))

    pdf_table = PdfTable(data, repeatRows=1)
    pdf_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8edf4")),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#b8c0cc")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        *[("ALIGN", (i, 1), (i, -1), "RIGHT") for i in table.money_cols],
    ]))
    story.append(pdf_table)
    doc.build(story)
    return out.getvalue()
