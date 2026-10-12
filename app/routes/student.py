from pathlib import Path
from uuid import uuid4

from flask import (
    Blueprint,
    render_template,
    redirect,
    url_for,
    flash,
    request,
    current_app
)
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename

from app import db
from app.models import Student, DocumentType, DocumentRequest
from app.algorithms.lifecycle import (
    PAYMENT_VERIFICATION,
    FOR_CORRECTION
)


student_bp = Blueprint(
    'student',
    __name__,
    url_prefix='/student'
)

ALLOWED_RECEIPT_EXTENSIONS = {'jpg', 'jpeg', 'png', 'pdf'}
MAX_RECEIPT_SIZE = 5 * 1024 * 1024


def student_only():
    return isinstance(current_user._get_current_object(), Student)


def _own_request_or_none(request_id):
    doc_request = db.session.get(DocumentRequest, request_id)

    if doc_request is None:
        return None

    if doc_request.student_id != current_user.id:
        return None

    return doc_request


def _save_receipt(upload):
    if upload is None or not upload.filename:
        raise ValueError('Please upload your payment receipt.')

    filename = secure_filename(upload.filename)
    extension = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''

    if extension not in ALLOWED_RECEIPT_EXTENSIONS:
        raise ValueError('Only JPG, PNG, and PDF receipts are allowed.')

    content = upload.stream.read(MAX_RECEIPT_SIZE + 1)

    if not content:
        raise ValueError('The uploaded receipt is empty.')

    if len(content) > MAX_RECEIPT_SIZE:
        raise ValueError('The receipt must not exceed 5 MB.')

    # Check the actual file signature, not only its extension.
    valid = False

    if extension in {'jpg', 'jpeg'}:
        valid = content.startswith(b'\xff\xd8\xff')
    elif extension == 'png':
        valid = content.startswith(b'\x89PNG\r\n\x1a\n')
    elif extension == 'pdf':
        valid = content.startswith(b'%PDF-')

    if not valid:
        raise ValueError('The file does not match its selected format.')

    upload_folder = Path(current_app.instance_path) / 'receipts'
    upload_folder.mkdir(parents=True, exist_ok=True)

    stored_filename = f'{uuid4().hex}.{extension}'
    saved_path = upload_folder / stored_filename

    with saved_path.open('wb') as file:
        file.write(content)

    return stored_filename, saved_path


@student_bp.route('/home')
@login_required
def home():
    if not student_only():
        flash('Only students can access this page.')
        return redirect(url_for('staff.home'))

    requests = sorted(
        current_user.document_requests,
        key=lambda r: r.date_requested,
        reverse=True
    )

    document_types = (
        DocumentType.query
        .order_by(DocumentType.name)
        .all()
    )

    return render_template(
        'modals/studentside.html',
        requests=requests,
        document_types=document_types
    )


@student_bp.route(
    '/request-form/submit/<int:doc_type_id>',
    methods=['POST']
)
@login_required
def submit_request(doc_type_id):
    if not student_only():
        flash('Only students can submit document requests.')
        return redirect(url_for('staff.home'))

    doc_type = DocumentType.query.get_or_404(doc_type_id)

    receipt = request.files.get('receipt')
    saved_path = None

    try:
        receipt_filename, saved_path = _save_receipt(receipt)

        new_request = DocumentRequest(
            student_id=current_user.id,
            document_type_id=doc_type.id,
            status=PAYMENT_VERIFICATION,
            or_photo_path=receipt_filename,
            payment_method='Online'
        )

        db.session.add(new_request)
        db.session.commit()

        flash(
            f'Your request for {doc_type.name} has been submitted. '
            'Your receipt is awaiting Cashier verification.'
        )

    except ValueError as error:
        flash(str(error))

    except Exception:
        db.session.rollback()

        if saved_path is not None:
            saved_path.unlink(missing_ok=True)

        current_app.logger.exception('Document request submission failed')
        flash('Unable to submit your request.')

    return redirect(url_for('student.home'))


@student_bp.route('/profile/update', methods=['POST'])
@login_required
def update_profile():
    if not student_only():
        flash('Only students can update this profile.')
        return redirect(url_for('staff.home'))

    full_name = (request.form.get('full_name') or '').strip()
    email = (request.form.get('email') or '').strip()

    if not full_name or not email:
        flash('Full name and email are required.')
        return redirect(url_for('student.home'))

    try:
        current_user.full_name = full_name
        current_user.email = email

        db.session.commit()
        flash('Profile updated successfully.')

    except Exception:
        db.session.rollback()
        flash('Unable to update your profile.')

    return redirect(url_for('student.home'))


@student_bp.route(
    '/request/<int:request_id>/mark-paid',
    methods=['POST']
)
@login_required
def mark_paid(request_id):
    if not student_only():
        flash('Only students can perform this action.')
        return redirect(url_for('staff.home'))

    doc_request = _own_request_or_none(request_id)

    if doc_request is None:
        flash('Document request not found or access denied.')
        return redirect(url_for('student.home'))

    flash('Payment receipts are now submitted with new requests.')
    return redirect(url_for('student.home'))


@student_bp.route(
    '/request/<int:request_id>/cancel',
    methods=['POST']
)
@login_required
def cancel_request(request_id):
    if not student_only():
        flash('Only students can perform this action.')
        return redirect(url_for('staff.home'))

    doc_request = _own_request_or_none(request_id)

    if doc_request is None:
        flash('Document request not found or access denied.')
        return redirect(url_for('student.home'))

    flash('Request cancellation is not currently supported.')
    return redirect(url_for('student.home'))


@student_bp.route(
    '/request/<int:request_id>/resubmit',
    methods=['POST']
)
@login_required
def resubmit_request(request_id):
    if not student_only():
        flash('Only students can perform this action.')
        return redirect(url_for('staff.home'))

    doc_request = _own_request_or_none(request_id)

    if doc_request is None:
        flash('Document request not found or access denied.')
        return redirect(url_for('student.home'))

    if doc_request.status != FOR_CORRECTION:
        flash('This request does not require correction.')
        return redirect(url_for('student.home'))

    flash('Correction submission is not yet connected.')
    return redirect(url_for('student.home'))
