from flask import Blueprint, redirect, url_for, flash
from flask_login import login_required, current_user
from app import db
from app.decorators import staff_required
from app.models import DocumentRequest

cashier_bp = Blueprint('cashier', __name__, url_prefix='/cashier')


@cashier_bp.route('/request/<int:request_id>/accept', methods=['POST'])
@login_required
@staff_required
def accept_request(request_id):
    if current_user.role != 'cashier':
        flash('Only cashier accounts can perform this action.')
        return redirect(url_for('staff.home'))

    doc_request = DocumentRequest.query.get_or_404(request_id)

    if doc_request.status != 'OR Review':
        flash('This request is not awaiting cashier review.')
        return redirect(url_for('staff.home'))

    doc_request.status = 'In Process'
    doc_request.handled_by = current_user.id
    db.session.commit()

    flash('Request approved and sent to the Registrar.')
    return redirect(url_for('staff.home'))