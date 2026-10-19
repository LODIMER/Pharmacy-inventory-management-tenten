from datetime import datetime, date, timedelta
from flask import request
from flask_login import current_user
from app import db
from app.models import AuditLog, Activity, Alert, Product, Batch


def client_ip():
    return request.headers.get("X-Forwarded-For", request.remote_addr or "")


def workstation():
    return request.user_agent.string[:80] if request.user_agent else "unknown"


def log_audit(action, entity=None, entity_id=None, details=None, before=None, after=None):
    uid = current_user.id if current_user.is_authenticated else None
    entry = AuditLog(
        user_id=uid,
        ip_address=client_ip(),
        workstation=workstation(),
        action=action,
        entity=entity,
        entity_id=str(entity_id) if entity_id is not None else None,
        details=details,
        before_value=str(before) if before is not None else None,
        after_value=str(after) if after is not None else None,
    )
    db.session.add(entry)


def add_activity(message, kind="info"):
    uid = current_user.id if current_user.is_authenticated else None
    db.session.add(Activity(message=message, kind=kind, user_id=uid))


def next_number(prefix, model, field):
    last = model.query.order_by(model.id.desc()).first()
    n = (last.id + 1) if last else 1
    return f"{prefix}-{n:05d}"


def inventory_value():
    total = 0.0
    batches = Batch.query.filter_by(status="available").all()
    for b in batches:
        total += b.quantity * (b.product.unit_cost or 0)
    return total


def expiry_buckets():
    today = date.today()
    buckets = {30: 0, 60: 0, 90: 0}
    batches = Batch.query.filter_by(status="available").all()
    for b in batches:
        days = (b.expiry_date - today).days
        if 0 <= days <= 30:
            buckets[30] += 1
        if 0 <= days <= 60:
            buckets[60] += 1
        if 0 <= days <= 90:
            buckets[90] += 1
    return buckets


def refresh_stock_alerts():
    products = Product.query.filter_by(is_active=True).all()
    for p in products:
        qty = p.available_qty()
        if qty <= 0:
            exists = Alert.query.filter_by(
                product_id=p.id, alert_type="out", is_read=False
            ).first()
            if not exists:
                db.session.add(
                    Alert(
                        product_id=p.id,
                        alert_type="out",
                        message=f"{p.brand_name} is out of stock.",
                    )
                )
        elif qty <= p.reorder_point:
            exists = Alert.query.filter_by(
                product_id=p.id, alert_type="low", is_read=False
            ).first()
            if not exists:
                db.session.add(
                    Alert(
                        product_id=p.id,
                        alert_type="low",
                        message=f"{p.brand_name} is running low ({qty} remaining, reorder at {p.reorder_point}).",
                    )
                )
        else:
            Alert.query.filter(
                Alert.product_id == p.id,
                Alert.alert_type.in_(("low", "out")),
                Alert.is_read.is_(False),
            ).update({"is_read": True})


def fefo_batch(product_id, needed=1):
    today = date.today()
    return (
        Batch.query.filter(
            Batch.product_id == product_id,
            Batch.status == "available",
            Batch.quantity >= needed,
            Batch.expiry_date >= today,
        )
        .order_by(Batch.expiry_date.asc())
        .first()
    )


def days_from_today(n):
    return date.today() + timedelta(days=n)
