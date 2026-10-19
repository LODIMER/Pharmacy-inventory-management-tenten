from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
from app import db
from app.models import User
from app.utils import log_audit

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.home"))
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        user = User.query.filter_by(username=username).first()
        if not user or not user.check_password(password):
            log_audit("Login Failed", "User", username, details="Invalid credentials")
            db.session.commit()
            flash("Invalid username or password.", "error")
            return render_template("login.html")
        if not user.is_active:
            flash("This account is disabled. Contact an administrator.", "error")
            return render_template("login.html")
        login_user(user)
        user.last_login = datetime.utcnow()
        log_audit("Login", "User", user.id, details=f"{user.username} signed in")
        db.session.commit()
        return redirect(url_for("dashboard.home"))
    return render_template("login.html")


@auth_bp.route("/logout")
@login_required
def logout():
    log_audit("Logout", "User", current_user.id)
    db.session.commit()
    logout_user()
    flash("You have been signed out.", "success")
    return redirect(url_for("auth.login"))
