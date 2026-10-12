from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user

from app import db
from app.decorators import staff_required
from app.models import DocumentRequest, StatusHistory, PreparationQueue
from app.services.lifecycle_service import change_request_state
from app.services.preparation_service import QUEUED, ACTIVE, PENDING
from app.algorithms.hrrn import calculate_hrrn_schedule
from app.algorithms.lifecycle import (
    PAYMENT_VERIFICATION,
    REQUEST_VERIFICATION,
    DOCUMENT_PREPARATION,
    READY_FOR_RELEASE,
    COMPLETED,
    FOR_CORRECTION,
    ON_HOLD,
    REJECTED,
)


staff_bp = Blueprint('staff', __name__, url_prefix='/staff')


# General staff actions.
# Verification, preparation, and release have dedicated routes.
STAFF_ACTIONS = {
    'cashier': {'correction_required', 'request_rejected'},
    'registrar': {'correction_required', 'request_rejected'},
}

REASON_REQUIRED = {'correction_required', 'request_rejected'}


def by_status(status, order=None):
    if order is None:
        order = DocumentRequest.date_requested

    return (
        DocumentRequest.query
        .filter_by(status=status)
        .order_by(order)
        .all()
    )


def preparation_by_internal_status(status):
    return (
        DocumentRequest.query
        .join(
            PreparationQueue,
            PreparationQueue.document_request_id == DocumentRequest.id
        )
        .filter(
            DocumentRequest.status == DOCUMENT_PREPARATION,
            PreparationQueue.status == status,
        )
        .order_by(
            DocumentRequest.date_requested.asc(),
            DocumentRequest.id.asc()
        )
        .all()
    )


@staff_bp.route('/home')
@login_required
@staff_required
def home():
    context = {'role': current_user.role}

    if current_user.role == 'cashier':
        context['pending_requests'] = by_status(
            PAYMENT_VERIFICATION
        )

        verified_ids = (
            db.session.query(StatusHistory.document_request_id)
            .filter(
                StatusHistory.action == 'payment_verified',
                StatusHistory.accepted.is_(True),
            )
        )

        context['approved_requests'] = (
            DocumentRequest.query
            .filter(DocumentRequest.id.in_(verified_ids))
            .order_by(DocumentRequest.date_requested)
            .all()
        )

    elif current_user.role == 'registrar':
        context['verification_requests'] = by_status(
            REQUEST_VERIFICATION
        )

        context['preparation_requests'] = by_status(
            DOCUMENT_PREPARATION
        )

        context['queued_requests'] = preparation_by_internal_status(
            QUEUED
        )

        context['active_requests'] = preparation_by_internal_status(
            ACTIVE
        )

        context['pending_dependency_requests'] = (
            preparation_by_internal_status(PENDING)
        )

        context['release_requests'] = by_status(
            READY_FOR_RELEASE
        )

        context['on_hold_requests'] = by_status(
            ON_HOLD
        )

        context['completed_requests'] = by_status(
            COMPLETED,
            DocumentRequest.date_completed.desc()
        )

        context['rejected_requests'] = by_status(
            REJECTED
        )

        # Shared HRRN queue
        schedule = calculate_hrrn_schedule()

        context['hrrn_schedule'] = schedule

        context['hrrn_by_request'] = {
            item.request_id: item
            for item in schedule
        }

        context['next_hrrn_request_id'] = (
            schedule[0].request_id
            if schedule
            else None
        )

    return render_template(
        'modals/staff/staffside.html',
        **context
    )


@staff_bp.route(
    '/request/<int:request_id>/<action>',
    methods=['POST']
)
@login_required
@staff_required
def request_action(request_id, action):
    role = current_user.role

    if (
        current_user.is_disabled
        or action not in STAFF_ACTIONS.get(role, set())
    ):
        flash('Your role cannot perform this action.')
        return redirect(url_for('staff.home'))

    note = (request.form.get('note') or '').strip()

    if action in REASON_REQUIRED and not note:
        flash('Please enter a reason.')
        return redirect(url_for('staff.home'))

    document = db.session.get(DocumentRequest, request_id)

    if document is None:
        flash('Document request not found.')
        return redirect(url_for('staff.home'))

    # Cashier actions are limited to Payment Verification.
    if role == 'cashier':
        if document.status != PAYMENT_VERIFICATION:
            flash(
                'This request is not awaiting payment verification.'
            )
            return redirect(url_for('staff.home'))

    # Registrar correction/rejection actions are limited
    # to Request Verification.
    elif role == 'registrar':
        if document.status != REQUEST_VERIFICATION:
            flash(
                'This request is not awaiting document request verification.'
            )
            return redirect(url_for('staff.home'))

    try:
        change_request_state(
            request_id=request_id,
            event=action,
            actor=current_user,
            note=note,
        )

        flash('Request updated successfully.')

    except ValueError as error:
        flash(str(error))

    return redirect(url_for('staff.home'))
