from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, abort, current_app
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from pathlib import Path
from app import db
from app.models import Product, Requisition, RequisitionLine, REQ_STATUSES
from app.utils import log_audit, add_activity, next_number, fefo_batch, refresh_stock_alerts

requisitions_bp = Blueprint("requisitions", __name__, url_prefix="/requisitions")

FLOW = ["pending_review", "processing", "ready_for_pickup", "completed"]


@requisitions_bp.route("/")
@login_required
def index():
    if current_user.is_staff():
        reqs = Requisition.query.order_by(Requisition.created_at.desc()).all()
    else:
        reqs = (
            Requisition.query.filter_by(requester_id=current_user.id)
            .order_by(Requisition.created_at.desc())
            .all()
        )
    return render_template("requisitions/index.html", reqs=reqs)


@requisitions_bp.route("/new", methods=["GET", "POST"])
@login_required
def create():
    products = Product.query.filter_by(is_active=True).order_by(Product.brand_name).all()
    if request.method == "POST":
        req_type = "transfer" if current_user.role == "department" else "refill"
        req = Requisition(
            req_number=next_number("REQ", Requisition, "req_number"),
            requester_id=current_user.id,
            req_type=req_type,
            status="pending_review",
            fulfillment=request.form.get("fulfillment") or "pickup",
            pickup_time=request.form.get("pickup_time"),
            notes=request.form.get("notes"),
        )
        file = request.files.get("prescription")
        if file and file.filename:
            name = secure_filename(file.filename)
            dest = Path(current_app.config["UPLOAD_FOLDER"]) / f"{req.req_number}_{name}"
            file.save(dest)
            req.prescription_file = str(dest.name)
        db.session.add(req)
        db.session.flush()
        product_ids = request.form.getlist("product_id")
        qtys = request.form.getlist("quantity")
        for pid, qty in zip(product_ids, qtys):
            if not pid:
                continue
            db.session.add(
                RequisitionLine(
                    requisition_id=req.id,
                    product_id=int(pid),
                    quantity=int(qty or 1),
                )
            )
        if not req.lines:
            # SQLAlchemy may not have lines yet; count posted
            pass
        log_audit("Requisition Submitted", "Requisition", req.id, details=req.req_number)
        add_activity(f"{req.req_number} submitted by {current_user.full_name}.", "order")
        db.session.commit()
        flash("Request submitted. You can cancel it until processing begins.", "success")
        return redirect(url_for("requisitions.detail", req_id=req.id))
    return render_template("requisitions/form.html", products=products)


@requisitions_bp.route("/<int:req_id>")
@login_required
def detail(req_id):
    req = db.session.get(Requisition, req_id) or abort(404)
    if not current_user.is_staff() and req.requester_id != current_user.id:
        abort(403)
    return render_template("requisitions/detail.html", req=req, flow=FLOW)


@requisitions_bp.route("/<int:req_id>/cancel", methods=["POST"])
@login_required
def cancel(req_id):
    req = db.session.get(Requisition, req_id) or abort(404)
    if not current_user.is_staff() and req.requester_id != current_user.id:
        abort(403)
    if req.status != "pending_review":
        flash("Requests can only be cancelled before processing begins.", "error")
        return redirect(url_for("requisitions.detail", req_id=req.id))
    req.status = "cancelled"
    log_audit("Order Cancelled", "Requisition", req.id, details=req.req_number)
    db.session.commit()
    flash("Request cancelled.", "success")
    return redirect(url_for("requisitions.detail", req_id=req.id))


@requisitions_bp.route("/<int:req_id>/review", methods=["POST"])
@login_required
def review(req_id):
    if not current_user.can_approve():
        abort(403)
    req = db.session.get(Requisition, req_id) or abort(404)
    decision = request.form.get("decision")
    req.reviewed_by_id = current_user.id
    req.review_note = request.form.get("review_note")
    if decision == "reject":
        req.status = "rejected"
        log_audit("Requisition Rejected", "Requisition", req.id)
        add_activity(f"{req.req_number} rejected.", "order")
    else:
        req.status = "processing"
        log_audit("Requisition Approved", "Requisition", req.id)
        add_activity(f"{req.req_number} approved and moved to processing.", "order")
    db.session.commit()
    flash("Decision recorded.", "success")
    return redirect(url_for("requisitions.detail", req_id=req.id))


@requisitions_bp.route("/<int:req_id>/advance", methods=["POST"])
@login_required
def advance(req_id):
    if not current_user.can_dispense() and not current_user.can_approve():
        abort(403)
    req = db.session.get(Requisition, req_id) or abort(404)
    if req.status == "processing":
        req.status = "ready_for_pickup"
        add_activity(f"{req.req_number} is ready for pickup/delivery.", "order")
    elif req.status == "ready_for_pickup":
        # fulfill: deduct FEFO stock
        for line in req.lines:
            remaining = line.quantity
            while remaining > 0:
                batch = fefo_batch(line.product_id, 1)
                if not batch:
                    flash(f"Cannot complete: insufficient stock for {line.product.brand_name}.", "error")
                    db.session.rollback()
                    return redirect(url_for("requisitions.detail", req_id=req.id))
                take = min(remaining, batch.quantity)
                batch.quantity -= take
                remaining -= take
        req.status = "completed"
        refresh_stock_alerts()
        add_activity(f"{req.req_number} completed and stock deducted.", "order")
        log_audit("Requisition Completed", "Requisition", req.id)
    db.session.commit()
    flash("Status updated.", "success")
    return redirect(url_for("requisitions.detail", req_id=req.id))
