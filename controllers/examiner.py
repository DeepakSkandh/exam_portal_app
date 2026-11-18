from datetime import date, datetime
from flask import current_app as app, render_template, request, redirect, url_for, flash, abort
from flask_login import current_user
from controllers.utils import role_required, to_date, to_time
from models import db, Exam, Slot, Booking, Evaluation, Score


def my_slot_or_403(slot_id):

    slot = db.get_or_404(Slot, slot_id)
    if slot.examiner_id != current_user.id:
        abort(403)
    return slot


def check_slot_form(slot_id=None):
    
    slot_date = to_date(request.form.get("date"))
    start = to_time(request.form.get("start_time"))
    end = to_time(request.form.get("end_time"))
    capacity = int(request.form.get("capacity") or 0)

    if not slot_date or not start or not end:
        return None, "Date, start time and end time are required."
    if slot_date < date.today():
        return None, "Slot date can't be in the past."
    if end <= start:
        return None, "End time must be after start time."
    if capacity < 1:
        return None, "Capacity must be at least 1."

    
    clash = Slot.query.filter(Slot.examiner_id == current_user.id,
                              Slot.date == slot_date,
                              Slot.status != "Cancelled",
                              Slot.start_time < end,
                              Slot.end_time > start)
    if slot_id:
        clash = clash.filter(Slot.id != slot_id)
    if clash.first():
        return None, "You already have a slot overlapping this time."

    return (slot_date, start, end, capacity), None


@app.route("/examiner")
@role_required("examiner")
def examiner_dashboard():
    exams = current_user.assigned_exams
    my_slots = Slot.query.filter_by(examiner_id=current_user.id).all()
    my_bookings = Booking.query.join(Slot).filter(Slot.examiner_id == current_user.id,
                                                  Booking.status != "Cancelled").all()
    pending = [b for b in my_bookings if b.status == "Booked"]

    return render_template("examiner/dashboard.html", exams=exams, slot_count=len(my_slots),
                           booked_count=len(my_bookings), pending=pending)


@app.route("/examiner/exams/<int:exam_id>/slots", methods=["GET", "POST"])
@role_required("examiner")
def examiner_slots(exam_id):
    exam = db.get_or_404(Exam, exam_id)
    if exam not in current_user.assigned_exams:
        abort(403)

    if request.method == "POST":
        if not exam.slot_creation_open():
            flash("Slot creation is not open for this exam right now.", "warning")
            return redirect(url_for("examiner_slots", exam_id=exam.id))

        data, error = check_slot_form()
        if error:
            flash(error, "danger")
            return redirect(url_for("examiner_slots", exam_id=exam.id))

        slot_date, start, end, capacity = data
        slot = Slot(exam_id=exam.id, examiner_id=current_user.id, date=slot_date,
                    start_time=start, end_time=end, capacity=capacity)
        db.session.add(slot)
        db.session.commit()
        flash("Slot created.", "success")
        return redirect(url_for("examiner_slots", exam_id=exam.id))

    slots = Slot.query.filter_by(exam_id=exam.id, examiner_id=current_user.id) \
                      .order_by(Slot.date, Slot.start_time).all()
    return render_template("examiner/slots.html", exam=exam, slots=slots)


@app.route("/examiner/slots/<int:slot_id>/edit", methods=["GET", "POST"])
@role_required("examiner")
def edit_slot(slot_id):
    slot = my_slot_or_403(slot_id)
    if not slot.exam.slot_creation_open() or slot.booked_count > 0:
        flash("Slots can only be changed during slot creation, before anyone books.", "warning")
        return redirect(url_for("examiner_slots", exam_id=slot.exam_id))

    if request.method == "POST":
        data, error = check_slot_form(slot_id=slot.id)
        if error:
            flash(error, "danger")
            return redirect(url_for("edit_slot", slot_id=slot.id))

        slot.date, slot.start_time, slot.end_time, slot.capacity = data
        slot.refresh_status()
        db.session.commit()
        flash("Slot updated.", "success")
        return redirect(url_for("examiner_slots", exam_id=slot.exam_id))

    return render_template("examiner/slot_edit.html", slot=slot)


@app.route("/examiner/slots/<int:slot_id>/delete", methods=["POST"])
@role_required("examiner")
def delete_slot(slot_id):
    slot = my_slot_or_403(slot_id)
    exam_id = slot.exam_id
    if not slot.exam.slot_creation_open() or slot.booked_count > 0:
        flash("Slots can only be removed during slot creation, before anyone books.", "warning")
    else:
        db.session.delete(slot)
        db.session.commit()
        flash("Slot removed.", "success")
    return redirect(url_for("examiner_slots", exam_id=exam_id))


@app.route("/examiner/slots/<int:slot_id>/students")
@role_required("examiner")
def slot_students(slot_id):
    slot = my_slot_or_403(slot_id)
    bookings = [b for b in slot.bookings if b.status != "Cancelled"]
    return render_template("examiner/students.html", slot=slot, bookings=bookings)


@app.route("/examiner/bookings/<int:booking_id>/evaluate", methods=["GET", "POST"])
@role_required("examiner")
def evaluate(booking_id):
    booking = db.get_or_404(Booking, booking_id)
    
    if booking.slot.examiner_id != current_user.id:
        abort(403)

    exam = booking.exam
    back = url_for("slot_students", slot_id=booking.slot_id)

    if booking.status == "Cancelled":
        flash("This booking was cancelled.", "warning")
        return redirect(back)
    if not exam.rubrics:
        flash("Admin hasn't added rubrics for this exam yet.", "warning")
        return redirect(back)
    if booking.evaluation and exam.results_published:
        flash("Results are already published, marks can't be changed now.", "warning")
        return redirect(back)

    if request.method == "POST":
        evaluation = booking.evaluation or Evaluation(booking_id=booking.id)
        db.session.add(evaluation)
        evaluation.scores = []  

        total = 0
        for rubric in exam.rubrics:
            try:
                marks = float(request.form.get(f"marks_{rubric.id}", 0))
            except ValueError:
                marks = -1
            if marks < 0 or marks > rubric.max_marks:
                db.session.rollback()
                flash(f"Marks for '{rubric.criterion}' must be between 0 and {rubric.max_marks}.", "danger")
                return redirect(url_for("evaluate", booking_id=booking.id))
            evaluation.scores.append(Score(rubric_id=rubric.id, marks=marks))
            total += marks

        evaluation.total_marks = total
        evaluation.remarks = request.form.get("remarks", "").strip()
        evaluation.evaluated_at = datetime.now()
        booking.status = "Completed"
        db.session.commit()
        flash(f"Marks saved for {booking.student.name}.", "success")
        return redirect(back)

    # existing marks, to pre-fill the form when editing
    old = {s.rubric_id: s.marks for s in booking.evaluation.scores} if booking.evaluation else {}
    return render_template("examiner/evaluate.html", booking=booking, exam=exam, old=old)