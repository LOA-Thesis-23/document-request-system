from datetime import datetime, timedelta, timezone
from flask import Blueprint, redirect, url_for, flash
from flask_login import login_required, current_user
from app import db
from app.decorators import staff_required
from app.models import DocumentRequest

registrar_bp = Blueprint('registrar', __name__, url_prefix='/registrar')

# ⚙️ CHANGE THIS to adjust how long a "Releasing" request stays valid before
# auto-flipping to "Expired" if the student never gets it scanned/claimed.
# Currently short (1 minute) for easy testing — set to timedelta(days=7) for production.
RELEASING_EXPIRY_DURATION = timedelta(minutes=1)


def expire_stale_releasing_requests():
    """Checked on every registrar page load — no background scheduler yet, so this
    only runs when someone actually visits /staff/home as a registrar."""
    cutoff = datetime.now(timezone.utc) - RELEASING_EXPIRY_DURATION
    stale_requests = DocumentRequest.query.filter(
        DocumentRequest.status == 'Releasing',
        DocumentRequest.released_at.isnot(None),
        DocumentRequest.released_at < cutoff
    ).all()

    for req in stale_requests:
        req.status = 'Expired'

    if stale_requests:
        db.session.commit()


@registrar_bp.route('/request/<int:request_id>/claim', methods=['POST'])
@login_required
@staff_required
def claim_request(request_id):
    if current_user.role != 'registrar':
        flash('Only registrar accounts can perform this action.')
        return redirect(url_for('staff.home'))

    doc_request = DocumentRequest.query.get_or_404(request_id)

    if doc_request.status != 'In Process' or doc_request.handled_by is not None:
        flash('This request is no longer available to claim.')
        return redirect(url_for('staff.home'))

    doc_request.handled_by = current_user.id
    db.session.commit()

    flash('Request claimed.')
    return redirect(url_for('staff.home'))


@registrar_bp.route('/request/<int:request_id>/hold', methods=['POST'])
@login_required
@staff_required
def hold_request(request_id):
    if current_user.role != 'registrar':
        flash('Only registrar accounts can perform this action.')
        return redirect(url_for('staff.home'))

    doc_request = DocumentRequest.query.get_or_404(request_id)

    if doc_request.status != 'In Process':
        flash('This request cannot be put on hold right now.')
        return redirect(url_for('staff.home'))

    doc_request.status = 'On Hold'
    db.session.commit()

    flash('Request marked as On Hold.')
    return redirect(url_for('staff.home'))


@registrar_bp.route('/request/<int:request_id>/send-to-encoding', methods=['POST'])
@login_required
@staff_required
def send_to_encoding(request_id):
    if current_user.role != 'registrar':
        flash('Only registrar accounts can perform this action.')
        return redirect(url_for('staff.home'))

    doc_request = DocumentRequest.query.get_or_404(request_id)

    if doc_request.status != 'In Process' or doc_request.handled_by is None:
        flash('This request cannot be moved to Encoding right now.')
        return redirect(url_for('staff.home'))

    doc_request.status = 'Encoding'
    db.session.commit()

    flash('Request moved to Encoding.')
    return redirect(url_for('staff.home'))


@registrar_bp.route('/request/<int:request_id>/mark-done', methods=['POST'])
@login_required
@staff_required
def mark_encoding_done(request_id):
    if current_user.role != 'registrar':
        flash('Only registrar accounts can perform this action.')
        return redirect(url_for('staff.home'))

    doc_request = DocumentRequest.query.get_or_404(request_id)

    if doc_request.status != 'Encoding':
        flash('This request is not in Encoding.')
        return redirect(url_for('staff.home'))

    doc_request.status = 'Releasing'
    doc_request.released_at = datetime.now(timezone.utc)
    db.session.commit()

    flash('Request moved to Releasing.')
    return redirect(url_for('staff.home'))