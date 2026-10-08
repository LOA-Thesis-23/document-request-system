from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app import db
from app.decorators import staff_required
from app.fsm import STAFF_ACTIONS, REASON_REQUIRED, apply_transition
from app.models import DocumentRequest, StatusHistory

staff_bp = Blueprint('staff', __name__, url_prefix='/staff')


def by_status(status, order=None):
    order = order if order is not None else DocumentRequest.date_requested
    return DocumentRequest.query.filter_by(status=status).order_by(order).all()


@staff_bp.route('/home')
@login_required
@staff_required
def home():
    context = {'role': current_user.role}

    if current_user.role == 'cashier':
        context['pending_requests'] = by_status('Payment Verification')
        verified_ids = db.session.query(StatusHistory.document_request_id).filter(
            StatusHistory.action == 'payment_verified',
            StatusHistory.accepted.is_(True)
        )
        context['approved_requests'] = DocumentRequest.query.filter(
            DocumentRequest.id.in_(verified_ids)
        ).order_by(DocumentRequest.date_requested).all()

    elif current_user.role == 'registrar':
        context['verification_requests'] = by_status('Request Verification')
        context['preparation_requests'] = by_status('Document Preparation')
        context['release_requests'] = by_status('Ready for Release')
        context['on_hold_requests'] = by_status('On Hold')
        context['completed_requests'] = by_status('Completed', DocumentRequest.date_completed.desc())
        context['rejected_requests'] = by_status('Rejected')

    return render_template('modals/staffside.html', **context)


@staff_bp.route('/request/<int:request_id>/<action>', methods=['POST'])
@login_required
@staff_required
def request_action(request_id, action):
    if action not in STAFF_ACTIONS.get(current_user.role, set()):
        flash('Your role cannot perform this action.')
        return redirect(url_for('staff.home'))

    doc_request = DocumentRequest.query.get_or_404(request_id)
    note = (request.form.get('note') or '').strip() or None

    if action in REASON_REQUIRED and not note:
        flash('Please enter a reason.')
        return redirect(url_for('staff.home'))

    ok, message = apply_transition(doc_request, action, staff=current_user, note=note)
    flash(message)
    return redirect(url_for('staff.home'))