from flask import Blueprint, render_template
from flask_login import login_required, current_user
from app.decorators import staff_required
from app.models import DocumentRequest
from app.routes.registrar import expire_stale_releasing_requests

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
        expire_stale_releasing_requests()

        context['pending_requests'] = DocumentRequest.query.filter_by(status='In Process', handled_by=None).order_by(DocumentRequest.date_requested).all()
        context['in_process_requests'] = DocumentRequest.query.filter(
            DocumentRequest.status == 'In Process',
            DocumentRequest.handled_by.isnot(None)
        ).order_by(DocumentRequest.date_requested).all()
        context['encoding_requests'] = DocumentRequest.query.filter_by(status='Encoding').order_by(DocumentRequest.date_requested).all()
        context['releasing_requests'] = DocumentRequest.query.filter_by(status='Releasing').order_by(DocumentRequest.date_requested).all()
        context['completed_requests'] = DocumentRequest.query.filter_by(status='Claimed').order_by(DocumentRequest.date_completed.desc()).all()
        context['expired_requests'] = DocumentRequest.query.filter_by(status='Expired').order_by(DocumentRequest.date_requested).all()

    return render_template('modals/staffside.html', **context)