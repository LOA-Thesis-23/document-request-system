from flask import Blueprint, render_template
from flask_login import login_required, current_user

student_bp = Blueprint('student', __name__, url_prefix='/student')


@student_bp.route('/home')
@login_required
def home():
    requests = sorted(
        current_user.document_requests,
        key=lambda r: r.date_requested,
        reverse=True
    )
    return render_template('modals/studentside.html', requests=requests)