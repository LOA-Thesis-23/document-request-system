from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_required, current_user
from app import db, bcrypt
from app.decorators import admin_required
from app.models import Staff


admin_bp = Blueprint('admin', __name__, url_prefix='/admin')
VALID_STAFF_ROLES = ['registrar', 'cashier', 'admin']


@admin_bp.route('/home')
@login_required
@admin_required
def home():
    return render_template('modals/adminside.html', role=current_user.role)


@admin_bp.route('/staff/create', methods=['POST'])
@login_required
@admin_required
def create_staff():
    full_name = request.form.get('full_name')
    email = request.form.get('email')
    password = request.form.get('password')
    role = request.form.get('role')

    if not full_name or not email or not password or not role:
        flash('Please fill in all fields.')
        return redirect(url_for('admin.home'))

    if role not in VALID_STAFF_ROLES:
        flash('Invalid role selected.')
        return redirect(url_for('admin.home'))

    if Staff.query.filter_by(email=email).first():
        flash('Email is already registered.')
        return redirect(url_for('admin.home'))

    hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
    new_staff = Staff(full_name=full_name, email=email, password=hashed_password, role=role)
    db.session.add(new_staff)
    db.session.commit()

    flash(f'{role.capitalize()} account created for {email}.')
    return redirect(url_for('admin.home'))