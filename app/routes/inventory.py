from datetime import datetime, date
from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import login_required, current_user
from app import db
from app.models import (
    Product,
    Batch,
    PurchaseOrder,
    POLine,
    StockAdjustment,
    LOCATIONS,
    BATCH_STATUSES,
)
from app.decorators import staff_required
from app.utils import log_audit, add_activity, refresh_stock_alerts, fefo_batch

inventory_bp = Blueprint("inventory", __name__, url_prefix="/inventory")


@inventory_bp.route("/")
@staff_required
def index():
    q = request.args.get("q", "").strip()
    status = request.args.get("status", "available")
    query = Batch.query.join(Product)
    if status:
        query = query.filter(Batch.status == status)
    if q:
        like = f"%{q}%"
        query = query.filter(
            db.or_(Product.brand_name.ilike(like), Batch.lot_number.ilike(like))
        )
    batches = query.order_by(Batch.expiry_date.asc()).all()
    perpetual = {}
    for b in Batch.query.filter_by(status="available").all():
        perpetual[b.product_id] = perpetual.get(b.product_id, 0) + b.quantity
    products = {p.id: p for p in Product.query.all()}
    return render_template(
        "inventory/index.html",
        batches=batches,
        perpetual=perpetual,
        products=products,
        locations=LOCATIONS,
        statuses=BATCH_STATUSES,
        status=status,
        q=q,
        today=date.today(),
    )


@inventory_bp.route("/receive", methods=["GET", "POST"])
@staff_required
def receive():
    if not current_user.can_inventory():
        abort(403)
    pos = PurchaseOrder.query.filter(
        PurchaseOrder.status.in_(("submitted", "partially_received"))
    ).order_by(PurchaseOrder.id.desc()).all()
    products = Product.query.filter_by(is_active=True).order_by(Product.brand_name).all()
    if request.method == "POST":
        product_id = int(request.form["product_id"])
        qty = int(request.form.get("quantity") or 0)
        lot = request.form.get("lot_number")
        expiry = request.form.get("expiry_date")
        if qty <= 0 or not lot or not expiry:
            flash("Lot number, expiry, and quantity are required.", "error")
            return redirect(url_for("inventory.receive"))
        po_id = request.form.get("po_id") or None
        batch = Batch(
            product_id=product_id,
            lot_number=lot,
            mfg_date=date.fromisoformat(request.form["mfg_date"]) if request.form.get("mfg_date") else None,
            expiry_date=date.fromisoformat(expiry),
            location=request.form.get("location") or "Shelf",
            quantity=qty,
            status="available",
            po_id=int(po_id) if po_id else None,
            invoice_date=date.fromisoformat(request.form["invoice_date"])
            if request.form.get("invoice_date")
            else date.today(),
        )
        db.session.add(batch)
        if po_id:
            po = db.session.get(PurchaseOrder, int(po_id))
            line = POLine.query.filter_by(po_id=po.id, product_id=product_id).first()
            if line:
                line.qty_received += qty
            if po:
                lines = po.lines
                if all(l.qty_received >= l.qty_ordered for l in lines):
                    po.status = "completed"
                else:
                    po.status = "partially_received"
        product = db.session.get(Product, product_id)
        log_audit(
            "Stock Created",
            "Batch",
            lot,
            details=f"Received {qty} of {product.brand_name} lot {lot} (FEFO location {batch.location})",
        )
        add_activity(f"Received {qty} {product.uom} of {product.brand_name} (lot {lot}).", "receive")
        refresh_stock_alerts()
        db.session.commit()
        flash("Stock received and lot recorded.", "success")
        return redirect(url_for("inventory.index"))
    return render_template(
        "inventory/receive.html", pos=pos, products=products, locations=LOCATIONS
    )


@inventory_bp.route("/adjust/<int:batch_id>", methods=["GET", "POST"])
@staff_required
def adjust(batch_id):
    if not current_user.can_inventory():
        abort(403)
    batch = db.session.get(Batch, batch_id) or abort(404)
    if request.method == "POST":
        before = batch.quantity
        before_status = batch.status
        new_qty = int(request.form.get("quantity") or 0)
        new_status = request.form.get("status") or batch.status
        reason = request.form.get("reason") or "write_off"
        batch.quantity = max(0, new_qty)
        batch.status = new_status
        db.session.add(
            StockAdjustment(
                batch_id=batch.id,
                user_id=current_user.id,
                reason=reason,
                qty_before=before,
                qty_after=batch.quantity,
                notes=request.form.get("notes"),
            )
        )
        log_audit(
            "Batch Adjusted",
            "Batch",
            batch.id,
            details=reason,
            before=f"qty={before} status={before_status}",
            after=f"qty={batch.quantity} status={batch.status}",
        )
        add_activity(
            f"Adjusted lot {batch.lot_number} ({batch.product.brand_name}): {before} → {batch.quantity} ({reason}).",
            "adjust",
        )
        refresh_stock_alerts()
        db.session.commit()
        flash("Stock adjustment saved.", "success")
        return redirect(url_for("inventory.index"))
    return render_template("inventory/adjust.html", batch=batch, statuses=BATCH_STATUSES)
