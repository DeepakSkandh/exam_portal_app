from flask import current_app as app, render_template, request, redirect, url_for, flash
from controllers.utils import role_required
from models import db


@app.route("/admin")
@role_required("admin")
def admin_dashboard():
    return "Admin dashboard - coming in step 3"