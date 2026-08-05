from app import db, login_manager
from flask_login import UserMixin
from datetime import datetime, timezone

@login_manager.user_loader
def load_user(user_id):
    if user_id.startswith('staff_'):
        return Staff.query.get(int(user_id.split('_')[1]))
    if user_id.startswith('student_'):
        return Student.query.get(int(user_id.split('_')[1]))
    return None


class Student(db.Model, UserMixin):
    __tablename__ = 'students'

    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    birthdate = db.Column(db.Date, nullable=False)
    student_number = db.Column(db.String(50), unique=True, nullable=True)
    password = db.Column(db.String(255), nullable=False)
    status = db.Column(db.String(20), default='unverified')
    student_type = db.Column(db.String(20), nullable=True)
    date_created = db.Column(db.DateTime, default= lambda: datetime.now(timezone.utc))

    def get_id(self):
        return f'student_{self.id}'

class Staff(db.Model, UserMixin):
    __tablename__ = 'staff'

    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(50), nullable=False)
    date_created = db.Column(db.DateTime, default= lambda: datetime.now(timezone.utc))

    def get_id(self):
        return f'staff_{self.id}'