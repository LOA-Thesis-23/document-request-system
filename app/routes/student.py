from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app.fsm import apply_transition
from app import db
from app.models import DocumentType, DocumentRequest

student_bp = Blueprint('student', __name__, url_prefix='/student')


@student_bp.route('/home')
@login_required
def home():
    requests = sorted(
        current_user.document_requests,
        key=lambda r: r.date_requested,
        reverse=True
    )
    document_types = DocumentType.query.order_by(DocumentType.name).all()
    return render_template(
        'modals/studentside.html',
        requests=requests,
        document_types=document_types
    )


@student_bp.route('/request-form/submit/<int:doc_type_id>', methods=['POST'])
@login_required
def submit_request(doc_type_id):
    doc_type = DocumentType.query.get_or_404(doc_type_id)

    new_request = DocumentRequest(
        student_id=current_user.id,
        document_type_id=doc_type.id,
        status='Submitted'
    )
    db.session.add(new_request)
    db.session.commit()

    flash(f'Your request for {doc_type.name} has been submitted.')
    return redirect(url_for('student.home'))

@student_bp.route('/profile/update', methods=['POST'])
@login_required
def update_profile():
    current_user.full_name = request.form.get('full_name')
    current_user.email = request.form.get('email')
    db.session.commit()

    flash('Profile updated successfully.')
    return redirect(url_for('student.home'))

def _own_request_or_none(request_id):
    doc_request = DocumentRequest.query.get_or_404(request_id)
    return doc_request if doc_request.student_id == current_user.id else None


@student_bp.route('/request/<int:request_id>/mark-paid', methods=['POST'])
@login_required
def mark_paid(request_id):
    doc_request = _own_request_or_none(request_id)
    if not doc_request:
        flash("You don't have permission to update this request.")
        return redirect(url_for('student.home'))
    ok, message = apply_transition(doc_request, 'mark_paid', student=current_user)
    flash('Marked as paid. Your request is now with the Cashier.' if ok else message)
    return redirect(url_for('student.home'))


@student_bp.route('/request/<int:request_id>/cancel', methods=['POST'])
@login_required
def cancel_request(request_id):
    doc_request = _own_request_or_none(request_id)
    if not doc_request:
        flash("You don't have permission to update this request.")
        return redirect(url_for('student.home'))
    ok, message = apply_transition(doc_request, 'cancel', student=current_user)
    flash('Your request has been cancelled.' if ok else message)
    return redirect(url_for('student.home'))


@student_bp.route('/request/<int:request_id>/resubmit', methods=['POST'])
@login_required
def resubmit_request(request_id):
    doc_request = _own_request_or_none(request_id)
    if not doc_request:
        flash("You don't have permission to update this request.")
        return redirect(url_for('student.home'))

    # Goes back to whoever sent it for correction.
    if doc_request.correction_from == 'Payment Verification':
        action = 'corrected_payment_submitted'
    else:
        action = 'corrected_information_submitted'

    ok, message = apply_transition(doc_request, action, student=current_user)
    flash('Correction submitted.' if ok else message)
    return redirect(url_for('student.home'))