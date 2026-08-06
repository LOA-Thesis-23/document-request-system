from flask import Blueprint, render_template
from flask_login import login_required,logout_user
from flask import Blueprint, render_template, redirect, url_for, flash

staff_bp = Blueprint('staff', __name__, url_prefix='/staff')


@staff_bp.route('/home')
@login_required
def home():
    return render_template('modals/staffside.html')

@staff_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.')
    return redirect(url_for('index'))