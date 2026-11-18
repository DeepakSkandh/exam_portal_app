from flask import current_app as app, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from models import db, User


@app.route("/")
def home():
    if not current_user.is_authenticated:
        return redirect(url_for("login"))
    if current_user.role == "admin":
        return redirect(url_for("admin_dashboard"))
    if current_user.role == "examiner":
        return redirect(url_for("examiner_dashboard"))
    return redirect(url_for("student_dashboard"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = User.query.filter_by(email=email).first()

        if not user or not check_password_hash(user.password_hash, password):
            flash("Wrong email or password.", "danger")
            return redirect(url_for("login"))
        if user.status == "pending":
            flash("Your account is waiting for admin approval.", "warning")
            return redirect(url_for("login"))
        if user.status == "deactivated":
            flash("Your account has been deactivated. Contact the admin.", "danger")
            return redirect(url_for("login"))

        login_user(user)
        return redirect(url_for("home"))

    return render_template("login.html")


@app.route("/register/<role>", methods=["GET", "POST"])
def register(role):
    if role not in ("student", "examiner"):
        flash("Invalid registration type.", "danger")
        return redirect(url_for("login"))

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        phone = request.form.get("phone", "").strip()

        if not name or not email or len(password) < 4:
            flash("Fill all fields. Password must be at least 4 characters.", "danger")
            return redirect(url_for("register", role=role))
        if User.query.filter_by(email=email).first():
            flash("This email is already registered.", "danger")
            return redirect(url_for("register", role=role))

        user = User(name=name, email=email, phone=phone, role=role,
                    password_hash=generate_password_hash(password))
        if role == "examiner":
            user.department = request.form.get("department", "").strip()
            user.status = "pending"
        else:
            user.roll_no = request.form.get("roll_no", "").strip()
            user.status = "approved"

        db.session.add(user)
        db.session.commit()

        if role == "examiner":
            flash("Registered! Wait for admin approval before logging in.", "info")
        else:
            flash("Registered! You can log in now.", "success")
        return redirect(url_for("login"))

    return render_template("register.html", role=role)


@app.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    if request.method == "POST":
        current_user.name = request.form.get("name", "").strip() or current_user.name
        current_user.phone = request.form.get("phone", "").strip()
        if current_user.role == "student":
            current_user.roll_no = request.form.get("roll_no", "").strip()
        elif current_user.role == "examiner":
            current_user.department = request.form.get("department", "").strip()

        new_password = request.form.get("password", "")
        if new_password:
            if len(new_password) < 4:
                flash("Password must be at least 4 characters.", "danger")
                return redirect(url_for("profile"))
            current_user.password_hash = generate_password_hash(new_password)

        db.session.commit()
        flash("Profile updated.", "success")
        return redirect(url_for("profile"))

    return render_template("profile.html")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Logged out.", "info")
    return redirect(url_for("login"))