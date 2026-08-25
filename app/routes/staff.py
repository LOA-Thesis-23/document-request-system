from flask import Blueprint, render_template
from flask_login import login_required, current_user
from app.decorators import staff_required
from app.models import DocumentRequest

staff_bp = Blueprint('staff', __name__, url_prefix='/staff')


@staff_bp.route('/home')
@login_required
@staff_required
def home():
    context = {'role': current_user.role}

    if current_user.role == 'cashier':
        context['pending_requests'] = DocumentRequest.query.filter_by(status='OR Review').order_by(DocumentRequest.date_requested).all()
        context['approved_requests'] = DocumentRequest.query.filter_by(status='In Process').order_by(DocumentRequest.date_requested).all()
    elif current_user.role == 'registrar':
        context['pending_requests'] = DocumentRequest.query.filter_by(status='In Process').order_by(DocumentRequest.date_requested).all()

    return render_template('modals/staffside.html', **context)