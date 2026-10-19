from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import login_required, current_user
from app import db
from app.models import Supplier, PurchaseOrder, POLine, Product, SupplierReturn, Batch, PO_STATUSES
from app.decorators import staff_required
from app.utils import log_audit, add_activity, next_number, refresh_stock_alerts

suppliers_bp = Blueprint("suppliers", __name__, url_prefix="/suppliers")


@suppliers_bp.route("/")
@staff_required
def index():
    if not current_user.can_purchase():
        abort(403)
    suppliers = Supplier.query.order_by(Supplier.name).all()
    return render_template("suppliers/index.html", suppliers=suppliers)


@suppliers_bp.route("/new", methods=["GET", "POST"])
@staff_required
def create():
    if not current_user.can_purchase():
        abort(403)
    if request.method == "POST":
        s = Supplier(
            name=request.form.get("name"),
            contact_name=request.form.get("contact_name"),
            email=request.form.get("email"),
            phone=request.form.get("phone"),
            address=request.form.get("address"),
            lead_time_days=int(request.form.get("lead_time_days") or 7),
            payment_terms=request.form.get("payment_terms"),
        )
        db.session.add(s)
        log_audit("Supplier Created", "Supplier", details=s.name)
        db.session.commit()
        flash("Supplier added.", "success")
        return redirect(url_for("suppliers.index"))
    return render_template("suppliers/form.html", supplier=None)


@suppliers_bp.route("/<int:supplier_id>/edit", methods=["GET", "POST"])
@staff_required
def edit(supplier_id):
    if not current_user.can_purchase():
        abort(403)
    s = db.session.get(Supplier, supplier_id) or abort(404)
    if request.method == "POST":
        s.name = request.form.get("name")
        s.contact_name = request.form.get("contact_name")
        s.email = request.form.get("email")
        s.phone = request.form.get("phone")
        s.address = request.form.get("address")
        s.lead_time_days = int(request.form.get("lead_time_days") or 7)
        s.payment_terms = request.form.get("payment_terms")
        log_audit("Supplier Updated", "Supplier", s.id)
        db.session.commit()
        flash("Supplier updated.", "success")
        return redirect(url_for("suppliers.index"))
    return render_template("suppliers/form.html", supplier=s)


@suppliers_bp.route("/purchase-orders")
@staff_required
def po_index():
    if not current_user.can_purchase():
        abort(403)
    pos = PurchaseOrder.query.order_by(PurchaseOrder.id.desc()).all()
    return render_template("suppliers/po_index.html", pos=pos)


@suppliers_bp.route("/purchase-orders/new", methods=["GET", "POST"])
@staff_required
def po_new():
    if not current_user.can_purchase():
        abort(403)
    suppliers = Supplier.query.filter_by(is_active=True).all()
    products = Product.query.filter_by(is_active=True).order_by(Product.brand_name).all()
    if request.method == "POST":
        po = PurchaseOrder(
            po_number=next_number("PO", PurchaseOrder, "po_number"),
            supplier_id=int(request.form["supplier_id"]),
            status="draft",
            created_by_id=current_user.id,
            notes=request.form.get("notes"),
        )
        db.session.add(po)
        db.session.flush()
        pids = request.form.getlist("product_id")
        qtys = request.form.getlist("qty_ordered")
        costs = request.form.getlist("unit_cost")
        for pid, qty, cost in zip(pids, qtys, costs):
            if not pid:
                continue
            prod = db.session.get(Product, int(pid))
            db.session.add(
                POLine(
                    po_id=po.id,
                    product_id=int(pid),
                    qty_ordered=int(qty or 0),
                    unit_cost=float(cost or (prod.unit_cost if prod else 0)),
                )
            )
        log_audit("PO Created", "PurchaseOrder", po.id, details=po.po_number)
        add_activity(f"Draft purchase order {po.po_number} created.", "purchase")
        db.session.commit()
        flash("Purchase order created.", "success")
        return redirect(url_for("suppliers.po_detail", po_id=po.id))
    return render_template("suppliers/po_form.html", suppliers=suppliers, products=products)


@suppliers_bp.route("/purchase-orders/auto", methods=["POST"])
@staff_required
def po_auto():
    if not current_user.can_purchase():
        abort(403)
    supplier = Supplier.query.first()
    if not supplier:
        flash("Add a supplier first.", "error")
        return redirect(url_for("suppliers.index"))
    needed = [p for p in Product.query.filter_by(is_active=True).all() if p.stock_status() in ("low", "out")]
    if not needed:
        flash("No items are at or below reorder point.", "success")
        return redirect(url_for("suppliers.po_index"))
    po = PurchaseOrder(
        po_number=next_number("PO", PurchaseOrder, "po_number"),
        supplier_id=supplier.id,
        status="draft",
        created_by_id=current_user.id,
        notes="Auto-generated from PAR / reorder points.",
    )
    db.session.add(po)
    db.session.flush()
    for p in needed:
        qty = max(p.max_level - p.available_qty(), p.reorder_point)
        db.session.add(
            POLine(po_id=po.id, product_id=p.id, qty_ordered=qty, unit_cost=p.unit_cost)
        )
    log_audit("PO Auto-Generated", "PurchaseOrder", po.id, details=po.po_number)
    add_activity(f"Auto PO {po.po_number} created for {len(needed)} low/out items.", "purchase")
    db.session.commit()
    flash(f"Generated {po.po_number} from reorder points.", "success")
    return redirect(url_for("suppliers.po_detail", po_id=po.id))


@suppliers_bp.route("/purchase-orders/<int:po_id>")
@staff_required
def po_detail(po_id):
    if not current_user.can_purchase():
        abort(403)
    po = db.session.get(PurchaseOrder, po_id) or abort(404)
    return render_template("suppliers/po_detail.html", po=po, statuses=PO_STATUSES)


@suppliers_bp.route("/purchase-orders/<int:po_id>/status", methods=["POST"])
@staff_required
def po_status(po_id):
    if not current_user.can_purchase():
        abort(403)
    po = db.session.get(PurchaseOrder, po_id) or abort(404)
    status = request.form.get("status")
    if status in PO_STATUSES:
        before = po.status
        po.status = status
        log_audit("PO Status Changed", "PurchaseOrder", po.id, before=before, after=status)
        db.session.commit()
        flash("PO status updated.", "success")
    return redirect(url_for("suppliers.po_detail", po_id=po.id))


@suppliers_bp.route("/returns")
@staff_required
def returns():
    if not current_user.can_purchase():
        abort(403)
    items = SupplierReturn.query.order_by(SupplierReturn.created_at.desc()).all()
    return render_template("suppliers/returns.html", items=items)


@suppliers_bp.route("/returns/new", methods=["GET", "POST"])
@staff_required
def return_new():
    if not current_user.can_purchase():
        abort(403)
    suppliers = Supplier.query.all()
    batches = Batch.query.order_by(Batch.expiry_date).all()
    if request.method == "POST":
        batch = db.session.get(Batch, int(request.form["batch_id"]))
        qty = int(request.form.get("quantity") or 0)
        rec = SupplierReturn(
            return_number=next_number("RTN", SupplierReturn, "return_number"),
            supplier_id=int(request.form["supplier_id"]),
            batch_id=batch.id,
            quantity=qty,
            reason=request.form.get("reason") or "expired",
            credit_note=request.form.get("credit_note"),
            credit_amount=float(request.form.get("credit_amount") or 0),
            created_by_id=current_user.id,
        )
        db.session.add(rec)
        before = batch.quantity
        batch.quantity = max(0, batch.quantity - qty)
        batch.status = "returned"
        log_audit(
            "Return to Supplier",
            "Batch",
            batch.id,
            before=before,
            after=batch.quantity,
            details=rec.return_number,
        )
        add_activity(f"Reverse distribution {rec.return_number} recorded.", "purchase")
        refresh_stock_alerts()
        db.session.commit()
        flash("Supplier return / credit tracked.", "success")
        return redirect(url_for("suppliers.returns"))
    return render_template("suppliers/return_form.html", suppliers=suppliers, batches=batches)
