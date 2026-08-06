from flask import Blueprint, render_template
from flask_login import login_required,logout_user
from flask import Blueprint, render_template, redirect, url_for, flash
from app.models import Student
admin_bp = Blueprint('admin', __name__, url_prefix='/admin')


@admin_bp.route('/home')
@login_required
def home():
    return render_template('modals/adminside.html')


@admin_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.')
    return redirect(url_for('index'))