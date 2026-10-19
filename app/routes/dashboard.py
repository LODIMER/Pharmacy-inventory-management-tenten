from datetime import date, datetime, timedelta
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from sqlalchemy import func
from app import db
from app.models import (
    Product,
    Batch,
    Sale,
    Requisition,
    Activity,
    Alert,
    User,
)
from app.utils import inventory_value, expiry_buckets, refresh_stock_alerts
from app.decorators import staff_required

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("/")
@login_required
def home():
    if current_user.is_staff():
        return redirect(url_for("dashboard.staff"))
    return redirect(url_for("dashboard.customer"))


@dashboard_bp.route("/dashboard")
@staff_required
def staff():
    refresh_stock_alerts()
    db.session.commit()

    products = Product.query.filter_by(is_active=True).all()
    active_skus = len(products)
    low = [p for p in products if p.stock_status() == "low"]
    out = [p for p in products if p.stock_status() == "out"]
    over = [p for p in products if p.stock_status() == "overstock"]
    expiry = expiry_buckets()

    start = datetime.combine(date.today(), datetime.min.time())
    today_sales = (
        db.session.query(func.coalesce(func.sum(Sale.total), 0)).filter(Sale.created_at >= start).scalar()
    )
    pending_rx = Requisition.query.filter(
        Requisition.status.in_(("pending_review", "processing"))
    ).count()
    received_today = Batch.query.filter(Batch.created_at >= start).count()
    activities = Activity.query.order_by(Activity.created_at.desc()).limit(12).all()
    alerts = (
        Alert.query.filter_by(is_read=False).order_by(Alert.created_at.desc()).limit(20).all()
    )

    return render_template(
        "dashboard_staff.html",
        inventory_value=inventory_value(),
        active_skus=active_skus,
        low=low,
        out=out,
        over=over,
        expiry=expiry,
        today_sales=today_sales,
        pending_rx=pending_rx,
        received_today=received_today,
        activities=activities,
        alerts=alerts,
    )


@dashboard_bp.route("/portal")
@login_required
def customer():
    if current_user.is_staff():
        return redirect(url_for("dashboard.staff"))
    pending = (
        Requisition.query.filter_by(requester_id=current_user.id)
        .filter(Requisition.status.in_(("pending_review", "processing", "ready_for_pickup")))
        .order_by(Requisition.created_at.desc())
        .all()
    )
    ready = [r for r in pending if r.status == "ready_for_pickup"]
    purchases = (
        Sale.query.filter_by(patient_id=current_user.id)
        .order_by(Sale.created_at.desc())
        .limit(8)
        .all()
    )
    history = (
        Requisition.query.filter_by(requester_id=current_user.id)
        .order_by(Requisition.created_at.desc())
        .limit(8)
        .all()
    )
    return render_template(
        "dashboard_customer.html",
        pending=pending,
        ready=ready,
        purchases=purchases,
        history=history,
    )


@dashboard_bp.route("/alerts/read/<int:alert_id>", methods=["POST"])
@staff_required
def mark_alert_read(alert_id):
    alert = db.session.get(Alert, alert_id)
    if alert:
        alert.is_read = True
        db.session.commit()
    return redirect(request.referrer or url_for("dashboard.staff"))
