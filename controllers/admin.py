from flask import current_app as app, render_template, request, redirect, url_for, flash, abort
from werkzeug.security import generate_password_hash
from controllers.utils import role_required, to_date
from models import db, User, Course, Exam, Rubric, Slot, Booking, Score

EXAM_TYPES = ["Viva", "Practical", "Project Demo", "Assessment"]
EXAM_STATUSES = ["Draft", "Slot Creation", "Booking Open", "Closed", "Completed"]


@app.route("/admin")
@role_required("admin")
def admin_dashboard():
    counts = {
        "Courses": Course.query.count(),
        "Examinations": Exam.query.count(),
        "Examiners": User.query.filter_by(role="examiner").count(),
        "Students": User.query.filter_by(role="student").count(),
        "Slots": Slot.query.count(),
        "Bookings": Booking.query.count(),
    }
    pending = User.query.filter_by(role="examiner", status="pending").all()
    return render_template("admin/dashboard.html", counts=counts, pending=pending)


@app.route("/admin/courses", methods=["GET", "POST"])
@role_required("admin")
def admin_courses():
    if request.method == "POST":
        code = request.form.get("code", "").strip().upper()
        name = request.form.get("name", "").strip()
        if not code or not name:
            flash("Course code and name are required.", "danger")
        elif Course.query.filter_by(code=code).first():
            flash("A course with this code already exists.", "danger")
        else:
            course = Course(code=code, name=name,
                            description=request.form.get("description", "").strip())
            db.session.add(course)
            db.session.commit()
            flash("Course added.", "success")
        return redirect(url_for("admin_courses"))

    courses = Course.query.order_by(Course.code).all()
    return render_template("admin/courses.html", courses=courses)


@app.route("/admin/courses/<int:course_id>/edit", methods=["GET", "POST"])
@role_required("admin")
def edit_course(course_id):
    course = db.get_or_404(Course, course_id)
    if request.method == "POST":
        code = request.form.get("code", "").strip().upper()
        other = Course.query.filter_by(code=code).first()
        if other and other.id != course.id:
            flash("Another course already uses this code.", "danger")
            return redirect(url_for("edit_course", course_id=course.id))

        course.code = code or course.code
        course.name = request.form.get("name", "").strip() or course.name
        course.description = request.form.get("description", "").strip()
        course.status = request.form.get("status", "Active")
        db.session.commit()
        flash("Course updated.", "success")
        return redirect(url_for("admin_courses"))

    return render_template("admin/course_edit.html", course=course)


@app.route("/admin/courses/<int:course_id>/delete", methods=["POST"])
@role_required("admin")
def delete_course(course_id):
    course = db.get_or_404(Course, course_id)
    if course.exams:
        flash("This course has examinations. Remove them first or mark it Inactive.", "warning")
    else:
        db.session.delete(course)
        db.session.commit()
        flash("Course removed.", "success")
    return redirect(url_for("admin_courses"))



@app.route("/admin/exams")
@role_required("admin")
def admin_exams():
    exams = Exam.query.order_by(Exam.id.desc()).all()
    return render_template("admin/exams.html", exams=exams, statuses=EXAM_STATUSES)


def fill_exam_from_form(exam):
    # used by both add and edit. returns an error message, or None if all good
    form = request.form
    exam.course_id = int(form.get("course_id"))
    exam.name = form.get("name", "").strip()
    exam.exam_type = form.get("exam_type")
    exam.duration = int(form.get("duration") or 0)
    exam.max_marks = int(form.get("max_marks") or 0)
    exam.slot_start = to_date(form.get("slot_start"))
    exam.slot_end = to_date(form.get("slot_end"))
    exam.booking_start = to_date(form.get("booking_start"))
    exam.booking_end = to_date(form.get("booking_end"))

    examiner_ids = [int(x) for x in form.getlist("examiners")]
    exam.examiners = User.query.filter(User.id.in_(examiner_ids)).all() if examiner_ids else []

    if not exam.name or exam.max_marks <= 0:
        return "Name and maximum marks are required."
    if exam.exam_type not in EXAM_TYPES:
        return "Choose a valid examination type."
    if None in (exam.slot_start, exam.slot_end, exam.booking_start, exam.booking_end):
        return "Please set all four timeline dates."
    if not (exam.slot_start <= exam.slot_end <= exam.booking_start <= exam.booking_end):
        return "Dates must be in order: slot creation start, slot creation end, booking start, booking end."
    return None


@app.route("/admin/exams/add", methods=["GET", "POST"])
@role_required("admin")
def add_exam():
    courses = Course.query.all()
    if not courses:
        flash("Add a course first.", "warning")
        return redirect(url_for("admin_courses"))
    examiners = User.query.filter_by(role="examiner", status="approved").all()

    if request.method == "POST":
        exam = Exam()
        error = fill_exam_from_form(exam)
        if error:
            db.session.rollback()
            flash(error, "danger")
            return redirect(url_for("add_exam"))
        db.session.add(exam)
        db.session.commit()
        flash("Examination created.", "success")
        return redirect(url_for("admin_exams"))

    return render_template("admin/exam_form.html", exam=None, courses=courses,
                           examiners=examiners, types=EXAM_TYPES)


@app.route("/admin/exams/<int:exam_id>/edit", methods=["GET", "POST"])
@role_required("admin")
def edit_exam(exam_id):
    exam = db.get_or_404(Exam, exam_id)
    courses = Course.query.all()
    examiners = User.query.filter_by(role="examiner", status="approved").all()

    if request.method == "POST":
        error = fill_exam_from_form(exam)
        if error:
            db.session.rollback()
            flash(error, "danger")
            return redirect(url_for("edit_exam", exam_id=exam.id))
        db.session.commit()
        flash("Examination updated.", "success")
        return redirect(url_for("admin_exams"))

    return render_template("admin/exam_form.html", exam=exam, courses=courses,
                           examiners=examiners, types=EXAM_TYPES)


@app.route("/admin/exams/<int:exam_id>/delete", methods=["POST"])
@role_required("admin")
def delete_exam(exam_id):
    exam = db.get_or_404(Exam, exam_id)
    if Booking.query.filter_by(exam_id=exam.id).first():
        flash("Students have booked this exam, so it can't be removed. Mark it Closed instead.", "warning")
    else:
        db.session.delete(exam)
        db.session.commit()
        flash("Examination removed.", "success")
    return redirect(url_for("admin_exams"))


@app.route("/admin/exams/<int:exam_id>/status", methods=["POST"])
@role_required("admin")
def change_exam_status(exam_id):

    exam = db.get_or_404(Exam, exam_id)
    new_status = request.form.get("status")
    if new_status not in EXAM_STATUSES:
        flash("Invalid status.", "danger")
        return redirect(url_for("admin_exams"))

    exam.status = new_status
    if new_status == "Completed":
        for slot in exam.slots:
            if slot.status != "Cancelled":
                slot.status = "Completed"
    db.session.commit()
    flash(f"'{exam.name}' is now {new_status}.", "success")
    return redirect(url_for("admin_exams"))


@app.route("/admin/exams/<int:exam_id>/publish", methods=["POST"])
@role_required("admin")
def toggle_results(exam_id):
    exam = db.get_or_404(Exam, exam_id)
    exam.results_published = not exam.results_published
    db.session.commit()
    flash("Results published." if exam.results_published else "Results hidden.", "info")
    return redirect(url_for("admin_exams"))




@app.route("/admin/exams/<int:exam_id>/rubrics", methods=["GET", "POST"])
@role_required("admin")
def exam_rubrics(exam_id):
    exam = db.get_or_404(Exam, exam_id)
    used = sum(r.max_marks for r in exam.rubrics)

    if request.method == "POST":
        criterion = request.form.get("criterion", "").strip()
        max_marks = int(request.form.get("max_marks") or 0)
        weightage = int(request.form.get("weightage") or 0)

        if not criterion or max_marks <= 0:
            flash("Criterion name and marks are required.", "danger")
        elif used + max_marks > exam.max_marks:
            flash(f"Rubric total can't go above the exam's {exam.max_marks} marks.", "danger")
        else:
            rubric = Rubric(exam_id=exam.id, criterion=criterion, max_marks=max_marks,
                            weightage=weightage,
                            description=request.form.get("description", "").strip())
            db.session.add(rubric)
            db.session.commit()
            flash("Criterion added.", "success")
        return redirect(url_for("exam_rubrics", exam_id=exam.id))

    return render_template("admin/rubrics.html", exam=exam, total=used)


@app.route("/admin/rubrics/<int:rubric_id>/delete", methods=["POST"])
@role_required("admin")
def delete_rubric(rubric_id):
    rubric = db.get_or_404(Rubric, rubric_id)
    exam_id = rubric.exam_id
    if Score.query.filter_by(rubric_id=rubric.id).first():
        flash("Students are already evaluated on this criterion, it can't be removed.", "warning")
    else:
        db.session.delete(rubric)
        db.session.commit()
        flash("Criterion removed.", "success")
    return redirect(url_for("exam_rubrics", exam_id=exam_id))



@app.route("/admin/examiners", methods=["GET", "POST"])
@role_required("admin")
def admin_examiners():
    if request.method == "POST":
       
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        if not name or not email or len(password) < 4:
            flash("Fill all fields. Password must be at least 4 characters.", "danger")
        elif User.query.filter_by(email=email).first():
            flash("This email is already registered.", "danger")
        else:
            examiner = User(name=name, email=email, role="examiner", status="approved",
                            department=request.form.get("department", "").strip(),
                            password_hash=generate_password_hash(password))
            db.session.add(examiner)
            db.session.commit()
            flash("Examiner added.", "success")
        return redirect(url_for("admin_examiners"))

    examiners = User.query.filter_by(role="examiner").order_by(User.id).all()
    return render_template("admin/examiners.html", examiners=examiners)


@app.route("/admin/examiners/<int:user_id>/<action>", methods=["POST"])
@role_required("admin")
def examiner_action(user_id, action):
    examiner = db.get_or_404(User, user_id)
    if examiner.role != "examiner":
        abort(404)

    if action == "approve":
        examiner.status = "approved"
        flash(f"{examiner.name} approved.", "success")
    elif action == "deactivate":
        examiner.status = "deactivated"
        flash(f"{examiner.name} deactivated.", "warning")
    else:
        abort(404)

    db.session.commit()
    return redirect(request.referrer or url_for("admin_examiners"))