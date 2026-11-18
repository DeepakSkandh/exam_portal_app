from flask import current_app as app, render_template, request, redirect, url_for, flash
from flask_login import current_user
from controllers.utils import role_required
from models import db


@app.route("/examiner")
@role_required("examiner")
def examiner_dashboard():
    return "Examiner dashboard - coming in step 5"