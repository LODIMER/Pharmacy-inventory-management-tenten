from datetime import datetime, date
from flask import Blueprint, render_template, request, redirect, url_for, flash, abort, session
from flask_login import login_required, current_user
from app import db
from app.models import Product, Batch, Sale, SaleLine, User, CUSTOMER_ROLES, SALE_DISCOUNTS
from app.decorators import staff_required
from app.utils import log_audit, add_activity, refresh_stock_alerts, fefo_batch, next_number

dispensing_bp = Blueprint("dispensing", __name__, url_prefix="/dispense")
TAX_RATE = 0.12
SENIOR_PWD_RATE = 0.20


def _cart():
    return session.setdefault("cart", [])


@dispensing_bp.route("/", methods=["GET", "POST"])
@staff_required
def pos():
    if not current_user.can_dispense():
        abort(403)
    products = Product.query.filter_by(is_active=True).order_by(Product.brand_name).all()
    patients = User.query.filter(User.role.in_(CUSTOMER_ROLES)).order_by(User.full_name).all()
    staff = User.query.filter(User.role.in_(("admin", "chief_pharmacist", "dispensing_staff"))).all()
    cart = session.get("cart", [])
    suggested = None
    if request.args.get("suggest"):
        pid = int(request.args.get("suggest"))
        suggested = fefo_batch(pid)
    return render_template(
        "dispensing/pos.html",
        products=products,
        patients=patients,
        staff=staff,
        cart=cart,
        discounts=SALE_DISCOUNTS,
        suggested=suggested,
        today=date.today(),
    )


@dispensing_bp.route("/add", methods=["POST"])
@staff_required
def add_line():
    if not current_user.can_dispense():
        abort(403)
    barcode = (request.form.get("barcode") or "").strip()
    product_id = request.form.get("product_id")
    qty = int(request.form.get("quantity") or 1)
    product = None
    if barcode:
        product = Product.query.filter(
            db.or_(Product.barcode == barcode, Product.ndc == barcode, Product.upc == barcode)
        ).first()
    elif product_id:
        product = db.session.get(Product, int(product_id))
    if not product:
        flash("Product not found.", "error")
        return redirect(url_for("dispensing.pos"))
    batch = fefo_batch(product.id, qty)
    if not batch:
        flash(f"{product.brand_name} has no FEFO-eligible batch with enough quantity.", "error")
        return redirect(url_for("dispensing.pos"))
    cart = session.get("cart", [])
    cart.append(
        {
            "product_id": product.id,
            "product_name": product.brand_name,
            "generic": product.generic_name,
            "batch_id": batch.id,
            "lot": batch.lot_number,
            "expiry": batch.expiry_date.isoformat(),
            "qty": qty,
            "unit_price": product.retail_price,
            "controlled": product.is_controlled,
            "schedule": product.schedule,
        }
    )
    session["cart"] = cart
    flash(f"Added {product.brand_name} from earliest-expiring lot {batch.lot_number}.", "success")
    return redirect(url_for("dispensing.pos"))


@dispensing_bp.route("/clear", methods=["POST"])
@staff_required
def clear():
    session["cart"] = []
    return redirect(url_for("dispensing.pos"))


@dispensing_bp.route("/complete", methods=["POST"])
@staff_required
def complete():
    if not current_user.can_dispense():
        abort(403)
    cart = session.get("cart", [])
    if not cart:
        flash("Cart is empty.", "error")
        return redirect(url_for("dispensing.pos"))
    needs_dual = any(i["controlled"] for i in cart)
    verifier_id = request.form.get("verifier_id")
    doctor_license = request.form.get("doctor_license")
    if needs_dual:
        if not verifier_id or int(verifier_id) == current_user.id:
            flash("Controlled substances require dual verification by a different licensed staff member.", "error")
            return redirect(url_for("dispensing.pos"))
        if not doctor_license:
            flash("Doctor license number is required for controlled substances.", "error")
            return redirect(url_for("dispensing.pos"))

    subtotal = sum(i["qty"] * i["unit_price"] for i in cart)
    discount_type = request.form.get("discount_type") or "None"
    discount_amount = subtotal * SENIOR_PWD_RATE if discount_type in ("Senior Citizen", "PWD") else 0
    taxable = subtotal - discount_amount
    tax = 0 if discount_type in ("Senior Citizen", "PWD") else taxable * TAX_RATE
    total = taxable + tax

    sale = Sale(
        receipt_no=next_number("RCP", Sale, "receipt_no"),
        patient_id=int(request.form["patient_id"]) if request.form.get("patient_id") else None,
        prescription_id=request.form.get("prescription_id"),
        dispenser_id=current_user.id,
        verifier_id=int(verifier_id) if verifier_id else None,
        doctor_license=doctor_license,
        discount_type=discount_type,
        discount_amount=round(discount_amount, 2),
        tax_amount=round(tax, 2),
        subtotal=round(subtotal, 2),
        total=round(total, 2),
    )
    db.session.add(sale)
    db.session.flush()
    for item in cart:
        batch = db.session.get(Batch, item["batch_id"])
        if not batch or batch.quantity < item["qty"]:
            db.session.rollback()
            flash("Insufficient stock on a selected batch.", "error")
            return redirect(url_for("dispensing.pos"))
        before = batch.quantity
        batch.quantity -= item["qty"]
        db.session.add(
            SaleLine(
                sale_id=sale.id,
                product_id=item["product_id"],
                batch_id=batch.id,
                quantity=item["qty"],
                unit_price=item["unit_price"],
                line_total=item["qty"] * item["unit_price"],
            )
        )
        log_audit(
            "Order Completed",
            "Batch",
            batch.id,
            details=f"Dispensed {item['qty']} {item['product_name']}",
            before=before,
            after=batch.quantity,
        )
    log_audit("Sale Posted", "Sale", sale.id, details=sale.receipt_no)
    add_activity(f"Sale {sale.receipt_no} posted (₱{sale.total:.2f}).", "sale")
    refresh_stock_alerts()
    db.session.commit()
    session["cart"] = []
    flash(f"Dispensed. Receipt {sale.receipt_no}.", "success")
    return redirect(url_for("dispensing.receipt", sale_id=sale.id))


@dispensing_bp.route("/receipt/<int:sale_id>")
@login_required
def receipt(sale_id):
    sale = db.session.get(Sale, sale_id) or abort(404)
    if not current_user.is_staff() and sale.patient_id != current_user.id:
        abort(403)
    return render_template("dispensing/receipt.html", sale=sale)


@dispensing_bp.route("/rts/<int:sale_id>", methods=["POST"])
@staff_required
def return_to_stock(sale_id):
    if not current_user.can_dispense():
        abort(403)
    sale = db.session.get(Sale, sale_id) or abort(404)
    for line in sale.lines:
        line.batch.quantity += line.quantity
    log_audit("Order Cancelled", "Sale", sale.id, details=f"RTS {sale.receipt_no}")
    add_activity(f"Return-to-stock processed for {sale.receipt_no}.", "adjust")
    refresh_stock_alerts()
    db.session.delete(sale)
    db.session.commit()
    flash("Uncollected prescription returned to stock.", "success")
    return redirect(url_for("dispensing.history"))


@dispensing_bp.route("/history")
@login_required
def history():
    if current_user.is_staff():
        sales = Sale.query.order_by(Sale.created_at.desc()).limit(100).all()
    else:
        sales = (
            Sale.query.filter_by(patient_id=current_user.id)
            .order_by(Sale.created_at.desc())
            .all()
        )
    return render_template("dispensing/history.html", sales=sales)
