from datetime import datetime, date
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin

db = SQLAlchemy()

exam_examiners = db.Table(
    "exam_examiners",
    db.Column("exam_id", db.Integer, db.ForeignKey("exam.id"), primary_key=True),
    db.Column("examiner_id", db.Integer, db.ForeignKey("user.id"), primary_key=True),
)


class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False)   
    phone = db.Column(db.String(20))
    department = db.Column(db.String(100))   
    roll_no = db.Column(db.String(30))       
    status = db.Column(db.String(20), default="approved")
    created_at = db.Column(db.DateTime, default=datetime.now)


class Course(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(20), unique=True, nullable=False)
    name = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text)
    status = db.Column(db.String(20), default="Active")

    exams = db.relationship("Exam", backref="course", cascade="all, delete-orphan")


class Exam(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey("course.id"), nullable=False)
    name = db.Column(db.String(150), nullable=False)
    exam_type = db.Column(db.String(30), nullable=False)  
    duration = db.Column(db.Integer)       
    max_marks = db.Column(db.Integer, nullable=False)
    slot_start = db.Column(db.Date)
    slot_end = db.Column(db.Date)
    booking_start = db.Column(db.Date)
    booking_end = db.Column(db.Date)
    
    status = db.Column(db.String(20), default="Draft")
    results_published = db.Column(db.Boolean, default=False)

    examiners = db.relationship("User", secondary=exam_examiners, backref="assigned_exams")
    rubrics = db.relationship("Rubric", backref="exam", cascade="all, delete-orphan")
    slots = db.relationship("Slot", backref="exam", cascade="all, delete-orphan")

    def slot_creation_open(self):
        today = date.today()
        return (self.status == "Slot Creation"
                and self.slot_start and self.slot_end
                and self.slot_start <= today <= self.slot_end)

    def booking_open(self):
        today = date.today()
        return (self.status == "Booking Open"
                and self.booking_start and self.booking_end
                and self.booking_start <= today <= self.booking_end)


class Rubric(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    exam_id = db.Column(db.Integer, db.ForeignKey("exam.id"), nullable=False)
    criterion = db.Column(db.String(100), nullable=False)
    max_marks = db.Column(db.Integer, nullable=False)
    weightage = db.Column(db.Integer, default=0)   
    description = db.Column(db.Text)


class Slot(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    exam_id = db.Column(db.Integer, db.ForeignKey("exam.id"), nullable=False)
    examiner_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    date = db.Column(db.Date, nullable=False)
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)
    capacity = db.Column(db.Integer, nullable=False)
    booked_count = db.Column(db.Integer, default=0)
    status = db.Column(db.String(20), default="Available")  

    examiner = db.relationship("User", backref="slots")
    bookings = db.relationship("Booking", backref="slot")

    @property
    def available_seats(self):
        return self.capacity - self.booked_count


class Booking(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    slot_id = db.Column(db.Integer, db.ForeignKey("slot.id"), nullable=False)
    exam_id = db.Column(db.Integer, db.ForeignKey("exam.id"), nullable=False)
    booked_at = db.Column(db.DateTime, default=datetime.now)
    status = db.Column(db.String(20), default="Booked")  
    note = db.Column(db.String(200))  

    student = db.relationship("User", backref="bookings")
    exam = db.relationship("Exam")
    evaluation = db.relationship("Evaluation", backref="booking", uselist=False)


class Evaluation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    booking_id = db.Column(db.Integer, db.ForeignKey("booking.id"), unique=True, nullable=False)
    total_marks = db.Column(db.Float, default=0)
    remarks = db.Column(db.Text)
    evaluated_at = db.Column(db.DateTime, default=datetime.now)

    scores = db.relationship("Score", backref="evaluation", cascade="all, delete-orphan")


class Score(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    evaluation_id = db.Column(db.Integer, db.ForeignKey("evaluation.id"), nullable=False)
    rubric_id = db.Column(db.Integer, db.ForeignKey("rubric.id"), nullable=False)
    marks = db.Column(db.Float, default=0)

    rubric = db.relationship("Rubric")