from flask import Blueprint, render_template
from flask_login import login_required

student_bp = Blueprint('student', __name__, url_prefix='/student')


@student_bp.route('/home')
@login_required
def home():
    return render_template('modals/studentside.html')