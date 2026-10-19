from flask import Blueprint, render_template, abort
from flask_login import login_required, current_user
from app.models import AuditLog
from app.decorators import staff_required

audit_bp = Blueprint("audit", __name__, url_prefix="/audit")


@audit_bp.route("/")
@staff_required
def index():
    logs = AuditLog.query.order_by(AuditLog.timestamp.desc()).limit(400).all()
    return render_template("audit/index.html", logs=logs)


@audit_bp.route("/me")
@login_required
def mine():
    logs = (
        AuditLog.query.filter_by(user_id=current_user.id)
        .order_by(AuditLog.timestamp.desc())
        .limit(200)
        .all()
    )
    return render_template("audit/mine.html", logs=logs)
