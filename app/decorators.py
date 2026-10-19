from functools import wraps
from flask import abort, flash, redirect, url_for
from flask_login import current_user


def staff_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for("auth.login"))
        if not current_user.is_staff():
            abort(403)
        return fn(*args, **kwargs)

    return wrapper


def roles_required(*roles):
    def deco(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if not current_user.is_authenticated:
                return redirect(url_for("auth.login"))
            if current_user.role not in roles:
                flash("You do not have permission for that action.", "error")
                abort(403)
            return fn(*args, **kwargs)

        return wrapper

    return deco


def customer_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for("auth.login"))
        if current_user.is_staff():
            abort(403)
        return fn(*args, **kwargs)

    return wrapper
