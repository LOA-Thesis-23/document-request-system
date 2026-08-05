from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_user, logout_user, login_required
from app import db, bcrypt
from app.models import Student

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        student = Student.query.filter_by(email=email).first()

        if student and bcrypt.check_password_hash(student.password, password):
            login_user(student)
            return redirect(url_for('auth.login'))  # placeholder redirect for now
        else:
            flash('Invalid email or password.')

    return render_template('modals/container.html')


@auth_bp.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        full_name = request.form.get('full_name')
        email = request.form.get('email')
        birthdate_str = request.form.get('birthdate')
        student_number = request.form.get('student_number') or None
        student_type = request.form.get('student_type')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')

        if password != confirm_password:
            flash('Passwords do not match.')
            return render_template('modals/container.html')

        if Student.query.filter_by(email=email).first():
            flash('Email is already registered.')
            return render_template('modals/container.html')

        if student_number and Student.query.filter_by(student_number=student_number).first():
            flash('Student number is already registered.')
            return render_template('modals/container.html')

        birthdate = datetime.strptime(birthdate_str, '%Y-%m-%d').date()

        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
        new_student = Student(
            full_name=full_name,
            email=email,
            birthdate=birthdate,
            student_number=student_number,
            student_type=student_type,
            password=hashed_password
        )
        db.session.add(new_student)
        db.session.commit()

        flash('Account created successfully.')
        return redirect(url_for('auth.login'))

    return render_template('modals/container.html')


@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('auth.login'))