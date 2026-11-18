from flask import current_app as app, render_template, request, redirect, url_for, flash
from flask_login import current_user
from controllers.utils import role_required
from models import db


@app.route("/student")
@role_required("student")
def student_dashboard():
    return "Student dashboard - coming in step 6"