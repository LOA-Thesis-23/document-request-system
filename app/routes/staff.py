from flask import Blueprint, render_template
from flask_login import login_required

staff_bp = Blueprint('staff', __name__, url_prefix='/staff')


@staff_bp.route('/home')
@login_required
def home():
    return render_template('modals/staffside.html')