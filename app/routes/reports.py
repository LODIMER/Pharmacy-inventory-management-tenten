from datetime import date, datetime, timedelta
from io import BytesIO, StringIO
from flask import (
    Blueprint,
    render_template,
    request,
    send_file,
    abort,
    Response,
)
from flask_login import login_required, current_user
from sqlalchemy import func
from openpyxl import Workbook
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from app import db
from app.models import Product, Batch, Sale, SaleLine, Requisition, RequisitionLine
from app.decorators import staff_required
from app.utils import inventory_value

reports_bp = Blueprint("reports", __name__, url_prefix="/reports")


def _abc():
    rows = (
        db.session.query(
            Product.id,
            Product.brand_name,
            func.coalesce(func.sum(SaleLine.quantity * SaleLine.unit_price), 0).label("revenue"),
        )
        .outerjoin(SaleLine, SaleLine.product_id == Product.id)
        .group_by(Product.id)
        .order_by(func.coalesce(func.sum(SaleLine.quantity * SaleLine.unit_price), 0).desc())
        .all()
    )
    total = sum(r.revenue for r in rows) or 1
    running = 0
    classified = []
    for r in rows:
        running += r.revenue
        share = running / total
        klass = "A" if share <= 0.8 else ("B" if share <= 0.95 else "C")
        classified.append({"name": r.brand_name, "revenue": r.revenue, "class": klass})
    return classified


@reports_bp.route("/")
@staff_required
def index():
    products = Product.query.filter_by(is_active=True).all()
    valuation = []
    for p in products:
        qty = p.available_qty()
        valuation.append(
            {
                "product": p,
                "qty": qty,
                "value": qty * (p.unit_cost or 0),
                "status": p.stock_status(),
            }
        )
    abc = _abc()
    expired = [
        b
        for b in Batch.query.all()
        if b.expiry_date < date.today() or b.status in ("quarantine", "damaged")
    ]
    start = datetime.combine(date.today().replace(day=1), datetime.min.time())
    month_sales = (
        db.session.query(func.coalesce(func.sum(Sale.total), 0)).filter(Sale.created_at >= start).scalar()
    )
    today_start = datetime.combine(date.today(), datetime.min.time())
    day_sales = (
        db.session.query(func.coalesce(func.sum(Sale.total), 0)).filter(Sale.created_at >= today_start).scalar()
    )
    top = (
        db.session.query(Product.brand_name, func.sum(SaleLine.quantity).label("qty"))
        .join(SaleLine, SaleLine.product_id == Product.id)
        .group_by(Product.id)
        .order_by(func.sum(SaleLine.quantity).desc())
        .limit(8)
        .all()
    )
    rx_otc = {"rx": 0, "otc": 0}
    for p in products:
        sold = sum(l.quantity for l in SaleLine.query.filter_by(product_id=p.id).all())
        if p.category == "OTC":
            rx_otc["otc"] += sold
        else:
            rx_otc["rx"] += sold
    controlled = (
        Sale.query.join(SaleLine)
        .join(Product)
        .filter(Product.is_controlled.is_(True))
        .order_by(Sale.created_at.desc())
        .all()
    )
    # unique
    seen = set()
    ctrl_sales = []
    for s in controlled:
        if s.id not in seen:
            seen.add(s.id)
            ctrl_sales.append(s)
    stockouts = [p for p in products if p.stock_status() == "out"]
    reorder = [p for p in products if p.stock_status() in ("low", "out")]
    return render_template(
        "reports/index.html",
        valuation=valuation,
        inventory_value=inventory_value(),
        abc=abc,
        expired=expired,
        month_sales=month_sales,
        day_sales=day_sales,
        top=top,
        rx_otc=rx_otc,
        ctrl_sales=ctrl_sales,
        stockouts=stockouts,
        reorder=reorder,
    )


@reports_bp.route("/department")
@login_required
def department():
    if current_user.role != "department" and not current_user.is_staff():
        abort(403)
    uid = current_user.id if current_user.role == "department" else request.args.get("user_id")
    query = Requisition.query.filter_by(req_type="transfer", status="completed")
    if current_user.role == "department":
        query = query.filter_by(requester_id=current_user.id)
    reqs = query.order_by(Requisition.created_at.desc()).all()
    usage = {}
    for r in reqs:
        for line in r.lines:
            usage[line.product.brand_name] = usage.get(line.product.brand_name, 0) + line.quantity
    return render_template("reports/department.html", reqs=reqs, usage=usage)


@reports_bp.route("/export/<fmt>/<kind>")
@staff_required
def export(fmt, kind):
    rows = _dataset(kind)
    filename = f"{kind}_{date.today().isoformat()}"
    if fmt == "csv":
        buf = StringIO()
        if rows:
            buf.write(",".join(rows[0].keys()) + "\n")
            for row in rows:
                buf.write(",".join(str(v).replace(",", " ") for v in row.values()) + "\n")
        return Response(
            buf.getvalue(),
            mimetype="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}.csv"},
        )
    if fmt == "xlsx":
        wb = Workbook()
        ws = wb.active
        ws.title = kind
        if rows:
            ws.append(list(rows[0].keys()))
            for row in rows:
                ws.append(list(row.values()))
        bio = BytesIO()
        wb.save(bio)
        bio.seek(0)
        return send_file(
            bio,
            as_attachment=True,
            download_name=f"{filename}.xlsx",
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    if fmt == "pdf":
        bio = BytesIO()
        c = canvas.Canvas(bio, pagesize=letter)
        width, height = letter
        y = height - 40
        c.setFont("Times-Bold", 14)
        c.drawString(40, y, f"MedVault Report — {kind.replace('_', ' ').title()}")
        y -= 24
        c.setFont("Times-Roman", 9)
        for row in rows[:60]:
            line = " | ".join(f"{k}: {v}" for k, v in row.items())
            c.drawString(40, y, line[:110])
            y -= 12
            if y < 40:
                c.showPage()
                y = height - 40
                c.setFont("Times-Roman", 9)
        c.save()
        bio.seek(0)
        return send_file(bio, as_attachment=True, download_name=f"{filename}.pdf", mimetype="application/pdf")
    abort(404)


def _dataset(kind):
    if kind == "valuation":
        return [
            {
                "sku": p.brand_name,
                "qty": p.available_qty(),
                "unit_cost": p.unit_cost,
                "value": round(p.available_qty() * (p.unit_cost or 0), 2),
            }
            for p in Product.query.filter_by(is_active=True).all()
        ]
    if kind == "abc":
        return [{"item": r["name"], "revenue": r["revenue"], "class": r["class"]} for r in _abc()]
    if kind == "sales":
        return [
            {
                "receipt": s.receipt_no,
                "total": s.total,
                "discount": s.discount_type,
                "when": s.created_at.isoformat(timespec="minutes"),
            }
            for s in Sale.query.order_by(Sale.created_at.desc()).limit(200).all()
        ]
    if kind == "controlled":
        data = []
        for s in Sale.query.order_by(Sale.created_at.desc()).all():
            for line in s.lines:
                if line.product.is_controlled:
                    data.append(
                        {
                            "receipt": s.receipt_no,
                            "drug": line.product.brand_name,
                            "schedule": line.product.schedule,
                            "qty": line.quantity,
                            "lot": line.batch.lot_number,
                            "doctor": s.doctor_license,
                            "dispenser": s.dispenser.username,
                            "verifier": s.verifier.username if s.verifier else "",
                        }
                    )
        return data
    if kind == "reorder":
        return [
            {
                "item": p.brand_name,
                "on_hand": p.available_qty(),
                "reorder_point": p.reorder_point,
                "status": p.stock_status(),
            }
            for p in Product.query.filter_by(is_active=True).all()
            if p.stock_status() in ("low", "out")
        ]
    abort(404)
