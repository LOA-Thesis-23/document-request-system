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

    return render_template('auth/login.html')


@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('auth.login'))