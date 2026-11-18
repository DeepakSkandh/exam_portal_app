from datetime import date
from flask import current_app as app, render_template, request, redirect, url_for, flash, abort
from flask_login import current_user
from sqlalchemy import or_
from controllers.utils import role_required
from controllers.admin import EXAM_TYPES
from models import db, Course, Exam, Slot, Booking


def active_booking_for(exam_id):
    # a booking that is not cancelled means the student already has this exam
    return Booking.query.filter(Booking.student_id == current_user.id,
                                Booking.exam_id == exam_id,
                                Booking.status != "Cancelled").first()


@app.route("/student")
@role_required("student")
def student_dashboard():
    today = date.today()

    open_exams = [e for e in Exam.query.filter_by(status="Booking Open").all() if e.booking_open()]
    open_slot_count = sum(1 for e in open_exams for s in e.slots if s.status == "Available")

    booked = [b for b in current_user.bookings if b.status == "Booked"]
    upcoming = [b for b in booked if b.slot.date >= today]
    upcoming.sort(key=lambda b: (b.slot.date, b.slot.start_time))

    results = [b for b in current_user.bookings if b.evaluation and b.exam.results_published]

    return render_template("student/dashboard.html", open_exams=open_exams,
                           open_slot_count=open_slot_count, upcoming=upcoming, results=results)


@app.route("/student/exams")
@role_required("student")
def student_exams():
    q = request.args.get("q", "").strip()
    exam_type = request.args.get("type", "")
    course_id = request.args.get("course", "")

    # students never see draft exams
    query = Exam.query.join(Course).filter(Exam.status != "Draft")
    if q:
        like = f"%{q}%"
        query = query.filter(or_(Exam.name.ilike(like), Course.code.ilike(like), Course.name.ilike(like)))
    if exam_type:
        query = query.filter(Exam.exam_type == exam_type)
    if course_id.isdigit():
        query = query.filter(Exam.course_id == int(course_id))

    exams = query.order_by(Exam.booking_start).all()
    my_exam_ids = {b.exam_id for b in current_user.bookings if b.status != "Cancelled"}

    return render_template("student/exams.html", exams=exams, my_exam_ids=my_exam_ids,
                           courses=Course.query.all(), types=EXAM_TYPES,
                           q=q, exam_type=exam_type, course_id=course_id)


@app.route("/student/exams/<int:exam_id>")
@role_required("student")
def exam_slots(exam_id):
    exam = db.get_or_404(Exam, exam_id)
    if exam.status == "Draft":
        abort(404)

    slots = Slot.query.filter(Slot.exam_id == exam.id, Slot.status.in_(["Available", "Full"])) \
                      .order_by(Slot.date, Slot.start_time).all()
    existing = active_booking_for(exam.id)
    return render_template("student/slots.html", exam=exam, slots=slots, existing=existing)


@app.route("/student/slots/<int:slot_id>/book", methods=["POST"])
@role_required("student")
def book_slot(slot_id):
    slot = db.get_or_404(Slot, slot_id)
    exam = slot.exam
    back = url_for("exam_slots", exam_id=exam.id)

    if not exam.booking_open():
        flash("Booking is not open for this exam.", "warning")
        return redirect(back)
    if active_booking_for(exam.id):
        flash("You have already booked a slot for this exam.", "warning")
        return redirect(back)
    if slot.status != "Available" or slot.booked_count >= slot.capacity:
        flash("Sorry, this slot is full.", "danger")
        return redirect(back)

    booking = Booking(student_id=current_user.id, slot_id=slot.id, exam_id=exam.id)
    slot.booked_count += 1
    slot.refresh_status()   # becomes Full when the last seat is taken
    db.session.add(booking)
    db.session.commit()
    flash(f"Booked {exam.name} on {slot.date} at {slot.start_time.strftime('%H:%M')}.", "success")
    return redirect(url_for("my_bookings"))


@app.route("/student/bookings")
@role_required("student")
def my_bookings():
    bookings = Booking.query.filter_by(student_id=current_user.id) \
                            .order_by(Booking.booked_at.desc()).all()
    return render_template("student/bookings.html", bookings=bookings)


@app.route("/student/bookings/<int:booking_id>/cancel", methods=["POST"])
@role_required("student")
def cancel_booking(booking_id):
    booking = db.get_or_404(Booking, booking_id)
    if booking.student_id != current_user.id:
        abort(403)

    if booking.status != "Booked":
        flash("Only active bookings can be cancelled.", "warning")
    elif not booking.exam.booking_open():
        flash("The booking deadline has passed, you can't cancel now.", "warning")
    else:
        booking.status = "Cancelled"   # never deleted, so history stays
        booking.slot.booked_count -= 1
        booking.slot.refresh_status()  # Full slot becomes Available again
        db.session.commit()
        flash("Booking cancelled.", "info")
    return redirect(url_for("my_bookings"))


@app.route("/student/results")
@role_required("student")
def student_results():
    done = Booking.query.filter_by(student_id=current_user.id, status="Completed").all()
    results = [b for b in done if b.evaluation and b.exam.results_published]
    return render_template("student/results.html", results=results)