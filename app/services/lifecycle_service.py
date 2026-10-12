from datetime import datetime, timezone

from app import db
from app.models import (
    DocumentRequest,
    StatusHistory,
    Staff,
    Student,
    PreparationQueue,
)
from app.algorithms.lifecycle import transition
from app.services.preparation_service import (
    queue_request,
    finish_preparation,
    get_unresolved_dependencies,
    get_active_activity,
    ACTIVE,
    QUEUED,
    PENDING,
    utc_now,
    DEFAULT_EPT_MINUTES,
)


def change_request_state(
    request_id,
    event,
    actor,
    note=None,
    conditions=None
):
    conditions = conditions or {}

    document = db.session.get(DocumentRequest, request_id)

    if document is None:
        raise ValueError("Document request not found.")

    current_state = document.status

    # ----------------------------------------
    # Identify actor and permissions
    # ----------------------------------------

    if isinstance(actor, Staff):
        role = actor.role
        staff_id = actor.id
        student_id = None

        if actor.is_disabled:
            raise ValueError("Staff account is disabled.")

    elif isinstance(actor, Student):
        role = "student"
        staff_id = None
        student_id = actor.id

        if document.student_id != actor.id:
            raise ValueError(
                "You cannot modify another student's request."
            )

    else:
        raise ValueError("Invalid actor.")

    # ----------------------------------------
    # Prepare FSM context
    # ----------------------------------------

    context = {
        "correction_from": document.correction_from,
        "hold_from": document.hold_from,
    }

    context.update(conditions)

    # ----------------------------------------
    # Validate FSM transition
    # ----------------------------------------

    try:
        next_state = transition(
            current_state=current_state,
            event=event,
            context=context,
            role=role
        )

    except ValueError as error:
        db.session.rollback()

        history = StatusHistory(
            document_request_id=document.id,
            from_status=current_state,
            to_status=current_state,
            action=event,
            accepted=False,
            staff_id=staff_id,
            student_id=student_id,
            note=str(error)
        )

        db.session.add(history)
        db.session.commit()
        raise

    # ----------------------------------------
    # Validate preparation-specific conditions
    # ----------------------------------------

    preparation = None

    if event == "preparation_completed":
        preparation = PreparationQueue.query.filter_by(
            document_request_id=document.id
        ).first()

        if preparation is None:
            raise ValueError(
                "Preparation record does not exist."
            )

        if preparation.status != ACTIVE:
            raise ValueError(
                "Request must be actively prepared."
            )

        if not isinstance(actor, Staff):
            raise ValueError(
                "Only a Registrar can complete preparation."
            )

        if preparation.preparing_registrar_id != actor.id:
            raise ValueError(
                "Only the assigned preparing Registrar can complete preparation."
            )

        if get_unresolved_dependencies(document.id):
            raise ValueError(
                "Resolve outstanding dependencies first."
            )

        if get_active_activity(document.id) is None:
            raise ValueError(
                "No active preparation session found."
            )

    # Hold/resume must preserve internal preparation state.
    if event in ("hold_required", "hold_resolved"):
        if not isinstance(actor, Staff) or role != "registrar":
            raise ValueError("Only a Registrar can manage a preparation hold.")
        preparation = PreparationQueue.query.filter_by(
            document_request_id=document.id
        ).first()
        if preparation is None:
            raise ValueError("Preparation record does not exist.")
        if event == "hold_required":
            if preparation.status not in (QUEUED, ACTIVE, PENDING):
                raise ValueError("Preparation cannot be held in its current status.")
            if preparation.status in (ACTIVE, PENDING):
                if preparation.preparing_registrar_id != staff_id:
                    raise ValueError("Only the preparing Registrar can place this request on hold.")
            if preparation.status == ACTIVE and get_active_activity(document.id) is None:
                raise ValueError("No active preparation session found.")
        elif document.hold_from != "Document Preparation":
            raise ValueError("This hold did not originate in Document Preparation.")

    # ----------------------------------------
    # Apply FSM transition
    # ----------------------------------------

    now = datetime.now(timezone.utc)

    if event == "correction_required":
        document.correction_from = current_state
        document.correction_note = note

    elif event == "correction_submitted":
        document.correction_from = None

    elif event == "hold_required":
        document.hold_from = current_state
        document.hold_reason = note
        document.hold_started_at = now
        document.hold_resolved_at = None

    elif event == "hold_resolved":
        document.hold_resolved_at = now
        document.hold_from = None

    if next_state == "Completed":
        document.date_completed = now
        document.released_at = now

    # ----------------------------------------
    # Preparation operations
    # ----------------------------------------

    try:
        if event == "hold_required":
            # APT excludes time spent On Hold. Retain pending dependencies.
            if preparation.status == ACTIVE:
                get_active_activity(document.id).ended_at = utc_now()
                preparation.status = QUEUED
                preparation.preparing_registrar_id = None
            # Queued requests stay queued internally but are excluded from
            # HRRN while the main FSM state is On Hold.

        elif event == "hold_resolved":
            # A held active session is resumed through HRRN, never
            # restarted automatically. Reset WT on queue re-entry.
            if preparation.status == QUEUED:
                preparation.preparing_registrar_id = None
                preparation.queue_entered_at = utc_now()

        if event == "preparation_completed":
            # Closes the active preparation interval.
            # Does not commit independently.
            finish_preparation(
                request_id=document.id,
                staff_id=actor.id
            )

        document.status = next_state
        db.session.flush()

        if (
            event == "request_verified"
            and next_state == "Document Preparation"
        ):
            # Automatically queue newly verified requests.
            # The initial EPT is equal for all types.
            queue_request(
                request_id=document.id,
                estimated_minutes=DEFAULT_EPT_MINUTES,
                commit=False
            )

        history = StatusHistory(
            document_request_id=document.id,
            from_status=current_state,
            to_status=next_state,
            action=event,
            accepted=True,
            staff_id=staff_id,
            student_id=student_id,
            note=note
        )

        db.session.add(history)
        db.session.commit()

    except Exception:
        db.session.rollback()
        raise

    return document
