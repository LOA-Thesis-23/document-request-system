from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_user, logout_user, login_required
from app import db, bcrypt
from app.models import Student, Staff

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

VALID_STUDENT_TYPES = ['current', 'graduate', 'transferee', 'inactive']

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        full_name = request.form.get('full_name')
        email = request.form.get('email')
        birthdate = request.form.get('birthdate')
        student_number = request.form.get('student_number')
        password = request.form.get('password')
        student_type = request.form.get('student_type')

        if not full_name or not email or not birthdate or not password:
            flash('Please fill in all required fields.')
            return redirect(url_for('auth.register'))

        existing_student = Student.query.filter_by(email=email).first()

        if existing_student:
            flash('Email already registered. Please log in.')
            return redirect(url_for('auth.login'))
        
        if not student_number:
            student_number = None  # Set to None if not provided

        if student_type and student_type not in VALID_STUDENT_TYPES:
            flash('Invalid student type. Please select a valid option.')
            return redirect(url_for('auth.register'))

        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')

        new_student = Student(
            full_name=full_name,
            email=email,
            birthdate=birthdate,
            student_number=student_number,
            password=hashed_password,
            student_type=student_type,
            status="unverified"
        )
        try:
            db.session.add(new_student)
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            flash('An error occurred while registering. Please try again.')
            return redirect(url_for('auth.register'))

        flash('Registration successful! Please log in.')
        return redirect(url_for('index'))

    return render_template('auth/register.html')


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        staff = Staff.query.filter_by(email=email).first()
        
        if staff and bcrypt.check_password_hash(staff.password, password):
            login_user(staff)
            if staff.role == 'admin':
                return redirect(url_for('admin.home'))  # redirect for admin
            return redirect(url_for('staff.home'))

        student = Student.query.filter_by(email=email).first()

        if student and bcrypt.check_password_hash(student.password, password):
            login_user(student)
            return redirect(url_for('student.home'))  #  redirect for student
        else:
            flash('Invalid email or password.')

    return render_template('auth/login.html')

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.')
    return redirect(url_for('index'))