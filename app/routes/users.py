from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import login_required, current_user
from app import db
from app.models import User, ROLE_LABELS, ALL_ROLES, STAFF_ROLES
from app.decorators import roles_required
from app.utils import log_audit, add_activity

users_bp = Blueprint("users", __name__, url_prefix="/users")


@users_bp.route("/")
@roles_required("admin")
def index():
    q = request.args.get("q", "").strip()
    role = request.args.get("role", "")
    query = User.query
    if q:
        like = f"%{q}%"
        query = query.filter(
            db.or_(User.username.ilike(like), User.full_name.ilike(like), User.email.ilike(like))
        )
    if role:
        query = query.filter_by(role=role)
    users = query.order_by(User.role, User.username).all()
    return render_template("users/index.html", users=users, roles=ROLE_LABELS, q=q, role=role)


@users_bp.route("/new", methods=["GET", "POST"])
@roles_required("admin")
def create():
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        if not username or User.query.filter_by(username=username).first():
            flash("Username is required and must be unique.", "error")
            return render_template("users/form.html", user=None, roles=ROLE_LABELS)
        user = User(
            username=username,
            full_name=request.form.get("full_name") or username,
            email=request.form.get("email"),
            phone=request.form.get("phone"),
            role=request.form.get("role") if request.form.get("role") in ALL_ROLES else "patient",
            department_name=request.form.get("department_name"),
            prescription_notes=request.form.get("prescription_notes"),
            is_active=bool(request.form.get("is_active")),
        )
        password = request.form.get("password") or "changeme123"
        user.set_password(password)
        db.session.add(user)
        db.session.flush()
        log_audit("User Created", "User", user.id, details=f"{user.username} as {user.role}")
        add_activity(f"Account created for {user.full_name} ({user.role_label()}).", "user")
        db.session.commit()
        flash("User account created.", "success")
        return redirect(url_for("users.index"))
    return render_template("users/form.html", user=None, roles=ROLE_LABELS)


@users_bp.route("/<int:user_id>/edit", methods=["GET", "POST"])
@roles_required("admin")
def edit(user_id):
    user = db.session.get(User, user_id) or abort(404)
    if request.method == "POST":
        before = f"{user.role}|{user.is_active}"
        user.full_name = request.form.get("full_name") or user.full_name
        user.email = request.form.get("email")
        user.phone = request.form.get("phone")
        role = request.form.get("role")
        if role in ALL_ROLES:
            user.role = role
        user.department_name = request.form.get("department_name")
        user.prescription_notes = request.form.get("prescription_notes")
        user.is_active = bool(request.form.get("is_active"))
        log_audit(
            "Role Changed" if before.split("|")[0] != user.role else "User Updated",
            "User",
            user.id,
            before=before,
            after=f"{user.role}|{user.is_active}",
        )
        db.session.commit()
        flash("User updated.", "success")
        return redirect(url_for("users.index"))
    return render_template("users/form.html", user=user, roles=ROLE_LABELS)


@users_bp.route("/<int:user_id>/reset-password", methods=["POST"])
@roles_required("admin")
def reset_password(user_id):
    user = db.session.get(User, user_id) or abort(404)
    new_pw = request.form.get("password") or "changeme123"
    user.set_password(new_pw)
    log_audit("Password Reset", "User", user.id, details=f"Password reset for {user.username}")
    db.session.commit()
    flash(f"Password reset for {user.username}.", "success")
    return redirect(url_for("users.index"))


@users_bp.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    if request.method == "POST":
        current_user.email = request.form.get("email")
        current_user.phone = request.form.get("phone")
        if not current_user.is_staff():
            # customers may not edit others; they may update own contact only
            pass
        pw = request.form.get("password")
        if pw:
            current_user.set_password(pw)
            log_audit("Password Changed", "User", current_user.id)
        db.session.commit()
        flash("Profile saved.", "success")
        return redirect(url_for("users.profile"))
    return render_template("users/profile.html")
