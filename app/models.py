from app import db, login_manager
from flask_login import UserMixin
from datetime import datetime, timezone


@login_manager.user_loader
def load_user(user_id):
    if user_id.startswith('staff_'):
        return db.session.get(
            Staff, int(user_id.split('_')[1])
        )

    if user_id.startswith('student_'):
        return db.session.get(
            Student, int(user_id.split('_')[1])
        )

    return None


class Student(db.Model, UserMixin):
    __tablename__ = 'students'

    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(150), nullable=False)
    email = db.Column(
        db.String(150), unique=True, nullable=False
    )
    birthdate = db.Column(db.Date, nullable=False)
    student_number = db.Column(
        db.String(50), unique=True, nullable=True
    )
    password = db.Column(db.String(255), nullable=False)
    status = db.Column(
        db.String(20), default='unverified'
    )
    student_type = db.Column(db.String(20), nullable=True)
    date_created = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc)
    )

    def get_id(self):
        return f'student_{self.id}'


class Staff(db.Model, UserMixin):
    __tablename__ = 'staff'

    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(150), nullable=False)
    email = db.Column(
        db.String(150), unique=True, nullable=False
    )
    password = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(50), nullable=False)
    date_created = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc)
    )

    is_disabled = db.Column(
        db.Boolean, default=False, nullable=False
    )
    is_online = db.Column(
        db.Boolean, default=False, nullable=False
    )
    last_login = db.Column(db.DateTime, nullable=True)

    def get_id(self):
        return f'staff_{self.id}'


class DocumentType(db.Model):
    __tablename__ = 'document_types'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(
        db.String(100), unique=True, nullable=False
    )
    fee = db.Column(
        db.Numeric(10, 2), nullable=False
    )
    description = db.Column(db.Text, nullable=True)
    date_created = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc)
    )


class DocumentRequest(db.Model):
    __tablename__ = 'document_requests'

    id = db.Column(db.Integer, primary_key=True)

    student_id = db.Column(
        db.Integer,
        db.ForeignKey('students.id'),
        nullable=False
    )

    document_type_id = db.Column(
        db.Integer,
        db.ForeignKey('document_types.id'),
        nullable=False
    )

    # Main FSM lifecycle state
    status = db.Column(
        db.String(50),
        nullable=False,
        default="Payment Verification"
    )

    # Student-uploaded receipt filename
    or_photo_path = db.Column(
        db.String(255), nullable=True
    )

    # Official Receipt number entered by Cashier
    or_number = db.Column(
        db.String(100), nullable=True
    )

    payment_method = db.Column(
        db.String(50), nullable=True
    )

    remarks = db.Column(db.Text, nullable=True)

    date_requested = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc)
    )

    date_completed = db.Column(
        db.DateTime, nullable=True
    )

    handled_by = db.Column(
        db.Integer,
        db.ForeignKey('staff.id'),
        nullable=True
    )

    released_at = db.Column(
        db.DateTime, nullable=True
    )

    # For Correction tracking
    correction_from = db.Column(
        db.String(50), nullable=True
    )

    correction_note = db.Column(
        db.Text, nullable=True
    )

    # On Hold tracking
    hold_from = db.Column(
        db.String(50), nullable=True
    )

    hold_reason = db.Column(
        db.Text, nullable=True
    )

    hold_started_at = db.Column(
        db.DateTime, nullable=True
    )

    hold_resolved_at = db.Column(
        db.DateTime, nullable=True
    )

    # Relationships
    student = db.relationship(
        'Student',
        backref=db.backref(
            'document_requests', lazy=True
        )
    )

    document_type = db.relationship(
        'DocumentType',
        backref=db.backref(
            'document_requests', lazy=True
        )
    )

    staff = db.relationship(
        'Staff',
        backref=db.backref(
            'document_requests', lazy=True
        )
    )


class StatusHistory(db.Model):
    __tablename__ = 'status_history'

    id = db.Column(db.Integer, primary_key=True)

    document_request_id = db.Column(
        db.Integer,
        db.ForeignKey('document_requests.id'),
        nullable=False
    )

    from_status = db.Column(
        db.String(50), nullable=False
    )

    to_status = db.Column(
        db.String(50), nullable=False
    )

    action = db.Column(
        db.String(50), nullable=False
    )

    accepted = db.Column(
        db.Boolean,
        default=True,
        nullable=False
    )

    staff_id = db.Column(
        db.Integer,
        db.ForeignKey('staff.id'),
        nullable=True
    )

    student_id = db.Column(
        db.Integer,
        db.ForeignKey('students.id'),
        nullable=True
    )

    note = db.Column(db.Text, nullable=True)

    timestamp = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc)
    )

    document_request = db.relationship(
        'DocumentRequest',
        backref=db.backref(
            'status_history', lazy=True
        )
    )

    staff = db.relationship(
        'Staff',
        backref=db.backref(
            'status_changes', lazy=True
        )
    )

    student = db.relationship(
        'Student',
        backref=db.backref(
            'status_changes', lazy=True
        )
    )


class SystemSettings(db.Model):
    __tablename__ = 'system_settings'

    id = db.Column(db.Integer, primary_key=True)

    name = db.Column(
        db.String(100),
        unique=True,
        nullable=False
    )

    value = db.Column(
        db.Boolean,
        nullable=False
    )

    description = db.Column(
        db.Text, nullable=True
    )


# ============================================
# DOCUMENT PREPARATION MODELS
# ============================================

class PreparationQueue(db.Model):
    __tablename__ = 'preparation_queue'

    id = db.Column(db.Integer, primary_key=True)

    document_request_id = db.Column(
        db.Integer,
        db.ForeignKey('document_requests.id'),
        unique=True,
        nullable=False
    )

    # Queued, Active Preparation, Pending Dependencies
    status = db.Column(
        db.String(30),
        nullable=False,
        default='Queued'
    )

    original_ept_minutes = db.Column(
        db.Float,
        nullable=False
    )

    queue_entered_at = db.Column(
        db.DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )

    # Registrar responsible for the current preparation assignment.
    # NULL while in the shared HRRN queue.
    preparing_registrar_id = db.Column(
        db.Integer,
        db.ForeignKey('staff.id'),
        nullable=True
    )

    preparing_registrar = db.relationship(
        'Staff',
        foreign_keys=[preparing_registrar_id],
        backref=db.backref('assigned_preparations', lazy=True)
    )

    document_request = db.relationship(
        'DocumentRequest',
        backref=db.backref(
            'preparation_queue',
            uselist=False
        )
    )


class PreparationActivity(db.Model):
    __tablename__ = 'preparation_activities'

    id = db.Column(db.Integer, primary_key=True)

    document_request_id = db.Column(
        db.Integer,
        db.ForeignKey('document_requests.id'),
        nullable=False
    )

    started_at = db.Column(
        db.DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )

    ended_at = db.Column(
        db.DateTime,
        nullable=True
    )

    document_request = db.relationship(
        'DocumentRequest',
        backref=db.backref(
            'preparation_activities',
            lazy=True
        )
    )


class PreparationDependency(db.Model):
    __tablename__ = 'preparation_dependencies'

    id = db.Column(db.Integer, primary_key=True)

    document_request_id = db.Column(
        db.Integer,
        db.ForeignKey('document_requests.id'),
        nullable=False
    )

    description = db.Column(
        db.Text,
        nullable=False
    )

    created_at = db.Column(
        db.DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )

    resolved_at = db.Column(
        db.DateTime,
        nullable=True
    )

    document_request = db.relationship(
        'DocumentRequest',
        backref=db.backref(
            'preparation_dependencies',
            lazy=True
        )
    )
