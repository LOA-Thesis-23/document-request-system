
from datetime import datetime, timezone
import math

from app import db
from app.models import (
    DocumentRequest,
    PreparationQueue,
    PreparationActivity,
    PreparationDependency,
    Staff,
)


QUEUED = "Queued"
ACTIVE = "Active Preparation"
PENDING = "Pending Dependencies"
COMPLETED = "Completed"

DOCUMENT_PREPARATION = "Document Preparation"

# Temporary equal estimate for all document types.
# Update after consultation with the Registrar.
DEFAULT_EPT_MINUTES = 30.0


def utc_now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def normalize_utc(value):
    """Normalize database datetimes for elapsed-time calculations."""
    if value.tzinfo is not None:
        return value.astimezone(timezone.utc).replace(tzinfo=None)
    return value


def get_request(request_id):
    document = db.session.get(DocumentRequest, request_id)

    if document is None:
        raise ValueError("Document request not found.")

    return document


def get_preparation(request_id):
    preparation = PreparationQueue.query.filter_by(
        document_request_id=request_id
    ).first()

    if preparation is None:
        raise ValueError("Preparation record not found.")

    return preparation


def require_preparation_state(document):
    if document.status != DOCUMENT_PREPARATION:
        raise ValueError(
            "Request is not in Document Preparation."
        )


def require_available_registrar(staff_id):
    staff = db.session.get(Staff, staff_id)
    if staff is None or staff.role != "registrar" or staff.is_disabled:
        raise ValueError("An active Registrar account is required.")
    return staff


def require_preparing_registrar(preparation, staff_id):
    require_available_registrar(staff_id)
    if preparation.preparing_registrar_id != staff_id:
        raise ValueError(
            "Only the Registrar assigned to this preparation can manage it."
        )


def get_active_activity(request_id):
    return PreparationActivity.query.filter_by(
        document_request_id=request_id,
        ended_at=None
    ).first()


def get_unresolved_dependencies(request_id):
    return PreparationDependency.query.filter_by(
        document_request_id=request_id,
        resolved_at=None
    ).all()


def get_actual_preparation_minutes(request_id):
    activities = PreparationActivity.query.filter_by(
        document_request_id=request_id
    ).all()

    total_seconds = 0

    for activity in activities:
        if activity.ended_at is None:
            continue

        duration = (
            normalize_utc(activity.ended_at) - normalize_utc(activity.started_at)
        ).total_seconds()

        if duration > 0:
            total_seconds += duration

    return total_seconds / 60.0


def get_remaining_ept_minutes(request_id):
    preparation = get_preparation(request_id)

    actual_minutes = get_actual_preparation_minutes(
        request_id
    )

    return max(
        1.0,
        preparation.original_ept_minutes - actual_minutes
    )


def queue_request(
    request_id,
    estimated_minutes=DEFAULT_EPT_MINUTES,
    commit=True
):
    document = get_request(request_id)
    require_preparation_state(document)

    existing = PreparationQueue.query.filter_by(
        document_request_id=request_id
    ).first()

    if existing is not None:
        raise ValueError(
            "Request already has a preparation record."
        )

    try:
        estimated_minutes = float(estimated_minutes)
    except (TypeError, ValueError):
        raise ValueError(
            "Invalid estimated preparation time."
        )

    if (
        not math.isfinite(estimated_minutes)
        or estimated_minutes <= 0
    ):
        raise ValueError(
            "Estimated preparation time must be positive and finite."
        )

    preparation = PreparationQueue(
        document_request_id=request_id,
        status=QUEUED,
        preparing_registrar_id=None,
        original_ept_minutes=estimated_minutes,
        queue_entered_at=utc_now()
    )

    db.session.add(preparation)

    if commit:
        db.session.commit()

    return preparation


def start_preparation(request_id, staff_id):
    """Start an HRRN-selected queued request from the shared queue.

    Caller must lock the queue and verify the HRRN winner in the
    same transaction. This function commits that transaction.
    """
    require_available_registrar(staff_id)
    document = get_request(request_id)
    require_preparation_state(document)
    preparation = get_preparation(request_id)

    if preparation.status != QUEUED:
        raise ValueError("Only queued requests can start preparation.")

    if preparation.preparing_registrar_id is not None:
        raise ValueError("Queued request is already assigned for preparation.")

    if get_active_activity(request_id) is not None:
        raise ValueError("An active preparation session already exists.")

    if get_unresolved_dependencies(request_id):
        raise ValueError("Resolve outstanding dependencies first.")

    # Check the preparation owner, not the verification owner.
    active_session = (
        db.session.query(PreparationQueue)
        .join(
            DocumentRequest,
            PreparationQueue.document_request_id == DocumentRequest.id
        )
        .filter(
            DocumentRequest.status == DOCUMENT_PREPARATION,
            PreparationQueue.status == ACTIVE,
            PreparationQueue.preparing_registrar_id == staff_id
        )
        .first()
    )
    if active_session is not None:
        raise ValueError(
            "Registrar already has an active preparation session."
        )

    activity = PreparationActivity(
        document_request_id=request_id,
        started_at=utc_now()
    )
    preparation.preparing_registrar_id = staff_id
    preparation.status = ACTIVE
    db.session.add(activity)
    db.session.commit()
    return preparation


def pause_for_dependency(
    request_id,
    staff_id,
    description
):
    document = get_request(request_id)
    require_preparation_state(document)

    preparation = get_preparation(request_id)
    require_preparing_registrar(preparation, staff_id)

    if preparation.status != ACTIVE:
        raise ValueError(
            "Request must be actively prepared."
        )

    description = (description or "").strip()

    if not description:
        raise ValueError(
            "Dependency description is required."
        )

    activity = get_active_activity(request_id)

    if activity is None:
        raise ValueError(
            "No active preparation session found."
        )

    now = utc_now()

    activity.ended_at = now

    dependency = PreparationDependency(
        document_request_id=request_id,
        description=description,
        created_at=now
    )

    preparation.status = PENDING

    db.session.add(dependency)
    db.session.commit()

    return dependency


def resolve_dependency(
    request_id,
    dependency_id,
    staff_id
):
    document = get_request(request_id)
    require_preparation_state(document)

    preparation = get_preparation(request_id)
    require_preparing_registrar(preparation, staff_id)

    if preparation.status != PENDING:
        raise ValueError(
            "Request is not waiting for dependencies."
        )

    dependency = db.session.get(
        PreparationDependency,
        dependency_id
    )

    if (
        dependency is None
        or dependency.document_request_id != request_id
    ):
        raise ValueError("Dependency not found.")

    if dependency.resolved_at is not None:
        raise ValueError(
            "Dependency has already been resolved."
        )

    now = utc_now()
    dependency.resolved_at = now

    db.session.flush()

    remaining = get_unresolved_dependencies(request_id)

    if not remaining:
        preparation.status = QUEUED
        preparation.queue_entered_at = now
        preparation.preparing_registrar_id = None

    db.session.commit()

    return preparation


def requeue_preparation(request_id, staff_id):
    document = get_request(request_id)
    require_preparation_state(document)

    preparation = get_preparation(request_id)
    require_preparing_registrar(preparation, staff_id)

    if preparation.status != ACTIVE:
        raise ValueError(
            "Only active preparation can be requeued."
        )

    activity = get_active_activity(request_id)

    if activity is None:
        raise ValueError(
            "No active preparation session found."
        )

    if get_unresolved_dependencies(request_id):
        raise ValueError(
            "Resolve dependencies before requeueing."
        )

    now = utc_now()

    activity.ended_at = now
    preparation.status = QUEUED
    preparation.queue_entered_at = now
    preparation.preparing_registrar_id = None

    db.session.commit()

    return preparation


def finish_preparation(request_id, staff_id):
    document = get_request(request_id)
    require_preparation_state(document)

    preparation = get_preparation(request_id)
    require_preparing_registrar(preparation, staff_id)

    if preparation.status != ACTIVE:
        raise ValueError(
            "Request must be actively prepared."
        )

    if get_unresolved_dependencies(request_id):
        raise ValueError(
            "Resolve dependencies before completing preparation."
        )

    activity = get_active_activity(request_id)

    if activity is None:
        raise ValueError(
            "No active preparation session found."
        )

    # Close the active preparation interval.
    activity.ended_at = utc_now()

    # Mark internal preparation as completed.
    preparation.status = COMPLETED

    # Do not commit here.
    # lifecycle_service.py must commit this
    # together with the FSM transition.
    db.session.flush()

    return get_actual_preparation_minutes(request_id)


def get_queued_requests():
    return (
        db.session.query(PreparationQueue)
        .join(
            DocumentRequest,
            PreparationQueue.document_request_id
            == DocumentRequest.id
        )
        .filter(
            DocumentRequest.status == DOCUMENT_PREPARATION,
            PreparationQueue.status == QUEUED,
            PreparationQueue.preparing_registrar_id.is_(None)
        )
        .order_by(
            PreparationQueue.queue_entered_at.asc(),
            PreparationQueue.id.asc()
        )
        .all()
    )
