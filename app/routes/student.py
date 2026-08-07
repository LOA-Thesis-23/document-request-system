from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
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