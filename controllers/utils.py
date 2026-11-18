from functools import wraps
from flask import flash, redirect, url_for
from flask_login import current_user, logout_user
from datetime import datetime


def role_required(role):
    # put this on top of a route so only that role can open it
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if not current_user.is_authenticated:
                return redirect(url_for("login"))
            if current_user.status != "approved":
                # e.g. admin deactivated this examiner while they were logged in
                logout_user()
                flash("Your account is not active.", "danger")
                return redirect(url_for("login"))
            if current_user.role != role:
                flash("You are not allowed to open that page.", "danger")
                return redirect(url_for("home"))
            return f(*args, **kwargs)
        return wrapper
    return decorator

def to_date(text):
    
    if not text:
        return None
    return datetime.strptime(text, "%Y-%m-%d").date()


def to_time(text):
    
    if not text:
        return None
    return datetime.strptime(text, "%H:%M").time()