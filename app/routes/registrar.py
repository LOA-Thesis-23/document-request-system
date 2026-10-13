
from flask import Blueprint, current_app, redirect, url_for, flash, request
from flask_login import login_required, current_user

from app import db
from app.decorators import staff_required
from app.models import DocumentRequest, StatusHistory, PreparationQueue
from app.services.lifecycle_service import change_request_state
from app.algorithms.hrrn import get_next_request
from app.services.preparation_service import (
    start_preparation,
    pause_for_dependency,
    resolve_dependency,
    requeue_preparation,
    get_preparation,
    get_unresolved_dependencies,
    get_active_activity,
    QUEUED,
    ACTIVE,
    PENDING,
)

from app.algorithms.lifecycle import (
    REQUEST_VERIFICATION,
    DOCUMENT_PREPARATION,
    ON_HOLD,
)


registrar_bp = Blueprint(
    "registrar",
    __name__,
    url_prefix="/registrar"
)


def expire_stale_releasing_requests():
    return 0


def registrar_allowed():
    return (
        current_user.is_authenticated
        and current_user.role == "registrar"
        and not current_user.is_disabled
    )


def registrar_owns_request(doc_request):
    return doc_request.handled_by == current_user.id


def back_to_dashboard(message=None, category="warning"):
    if message:
        flash(message, category)

    return redirect(url_for("staff.home"))


def get_preparation_request(request_id, require_owner=True):
    if not registrar_allowed():
        raise ValueError("Registrar access required.")

    doc_request = db.session.get(
        DocumentRequest,
        request_id
    )

    if doc_request is None:
        raise ValueError("Document request not found.")

    if doc_request.status != DOCUMENT_PREPARATION:
        raise ValueError(
            "Request is not in Document Preparation."
        )

    preparation = get_preparation(request_id)
    if require_owner and preparation.preparing_registrar_id != current_user.id:
        raise ValueError("This preparation is assigned to another Registrar.")

    return doc_request


# ============================================
# REQUEST VERIFICATION
# ============================================

@registrar_bp.route(
    "/request/<int:request_id>/send-to-encoding",
    methods=["POST"]
)
@login_required
@staff_required
def send_to_encoding(request_id):
    if not registrar_allowed():
        return back_to_dashboard(
            "Registrar access required."
        )

    # Lock the verification row so two Registrars cannot verify it together.
    doc_request = (
        db.session.query(DocumentRequest)
        .filter(DocumentRequest.id == request_id)
        .with_for_update()
        .first()
    )

    if doc_request is None:
        db.session.rollback()
        return back_to_dashboard("Document request not found.")

    if doc_request.status != REQUEST_VERIFICATION:
        db.session.rollback()
        return back_to_dashboard("Request is not awaiting verification.")

    if doc_request.handled_by is not None:
        db.session.rollback()
        return back_to_dashboard("Request has already been verified or assigned.")

    if (
        not doc_request.or_number
        or not doc_request.or_number.strip()
    ):
        return back_to_dashboard(
            "Cannot verify request: OR number is missing."
        )

    payment_verified = StatusHistory.query.filter_by(
        document_request_id=doc_request.id,
        action="payment_verified",
        accepted=True
    ).first()

    if payment_verified is None:
        return back_to_dashboard(
            "Cannot verify request: payment approval "
            "was not recorded."
        )

    if request.form.get("confirm_requirements") != "yes":
        return back_to_dashboard(
            "Please confirm that all request "
            "requirements have been reviewed."
        )

    try:
        # Record the verifier in the same transaction as the FSM change.
        doc_request.handled_by = current_user.id
        change_request_state(
            request_id=request_id,
            event="request_verified",
            actor=current_user,
            note=(
                "Document request requirements manually "
                "reviewed and verified by Registrar."
            ),
            conditions={
                "request_valid": True
            }
        )

        return back_to_dashboard(
            "Request verified and added to "
            "Document Preparation.",
            "success"
        )

    except ValueError as error:
        db.session.rollback()
        return back_to_dashboard(str(error))

    except Exception:
        db.session.rollback()
        raise


# ============================================
# START PREPARATION
# ============================================

@registrar_bp.route(
    "/request/<int:request_id>/start-preparation",
    methods=["POST"]
)
@login_required
@staff_required
def start_document_preparation(request_id):
    try:
        get_preparation_request(request_id, require_owner=False)

        preparation = get_preparation(request_id)

        if preparation.status != QUEUED:
            raise ValueError(
                "Only queued requests can be started."
            )

        # Serialize starts against existing preparation queue rows.
        # Must be MySQL/InnoDB; use a dedicated scheduler lock for
        # full serialization with simultaneous queue insertions.
        db.session.query(PreparationQueue).order_by(
            PreparationQueue.id.asc()
        ).with_for_update().all()

        db.session.expire_all()
        preparation = get_preparation(request_id)
        if preparation.status != QUEUED or preparation.preparing_registrar_id is not None:
            raise ValueError("This request is no longer available in the queue.")

        next_request = get_next_request()
        if next_request is None:
            raise ValueError("There are no eligible queued requests.")

        if next_request.request_id != request_id:
            current_app.logger.info(
                "Start rejected: request %s is not next (expected %s)",
                request_id,
                next_request.request_id,
            )
            raise ValueError(
                "This request is not next in the queue. "
                "Please start the top request first."
            )

        start_preparation(
            request_id=request_id,
            staff_id=current_user.id
        )

        return back_to_dashboard(
            "Document preparation started.",
            "success"
        )

    except ValueError as error:
        db.session.rollback()
        return back_to_dashboard(str(error))

    except Exception:
        db.session.rollback()
        raise


# ============================================
# PAUSE FOR DEPENDENCIES
# ============================================

@registrar_bp.route(
    "/request/<int:request_id>/pause-preparation",
    methods=["POST"]
)
@login_required
@staff_required
def pause_document_preparation(request_id):
    try:
        get_preparation_request(request_id)

        description = (
            request.form.get("description") or ""
        ).strip()

        if not description:
            raise ValueError(
                "Please provide a dependency description."
            )

        pause_for_dependency(
            request_id=request_id,
            staff_id=current_user.id,
            description=description
        )

        return back_to_dashboard(
            "Preparation paused. Request is now "
            "Pending Dependencies.",
            "success"
        )

    except ValueError as error:
        db.session.rollback()
        return back_to_dashboard(str(error))

    except Exception:
        db.session.rollback()
        raise


# ============================================
# RESOLVE DEPENDENCY
# ============================================

@registrar_bp.route(
    "/request/<int:request_id>/dependency/"
    "<int:dependency_id>/resolve",
    methods=["POST"]
)
@login_required
@staff_required
def resolve_document_dependency(
    request_id,
    dependency_id
):
    try:
        get_preparation_request(request_id)

        preparation = resolve_dependency(
            request_id=request_id,
            dependency_id=dependency_id,
            staff_id=current_user.id
        )

        if preparation.status == QUEUED:
            message = (
                "All dependencies resolved. "
                "Request returned to the preparation queue."
            )
        else:
            message = (
                "Dependency resolved. Other dependencies "
                "are still pending."
            )

        return back_to_dashboard(
            message,
            "success"
        )

    except ValueError as error:
        db.session.rollback()
        return back_to_dashboard(str(error))

    except Exception:
        db.session.rollback()
        raise


# ============================================
# REQUEUE PREPARATION
# ============================================

@registrar_bp.route(
    "/request/<int:request_id>/requeue-preparation",
    methods=["POST"]
)
@login_required
@staff_required
def requeue_document_preparation(request_id):
    try:
        get_preparation_request(request_id)

        requeue_preparation(
            request_id=request_id,
            staff_id=current_user.id
        )

        return back_to_dashboard(
            "Request returned to the preparation queue.",
            "success"
        )

    except ValueError as error:
        db.session.rollback()
        return back_to_dashboard(str(error))

    except Exception:
        db.session.rollback()
        raise


# ============================================
# COMPLETE PREPARATION
# ============================================

@registrar_bp.route(
    "/request/<int:request_id>/mark-done",
    methods=["POST"]
)
@login_required
@staff_required
def mark_done(request_id):
    try:
        get_preparation_request(request_id)

        preparation = get_preparation(request_id)

        if preparation.preparing_registrar_id != current_user.id:
            raise ValueError("This preparation is assigned to another Registrar.")

        if preparation.status != ACTIVE:
            raise ValueError(
                "Request must be actively prepared "
                "before completion."
            )

        if get_unresolved_dependencies(request_id):
            raise ValueError(
                "Resolve all dependencies first."
            )

        if get_active_activity(request_id) is None:
            raise ValueError(
                "No active preparation session found."
            )

        if request.form.get("confirm_completed") != "yes":
            raise ValueError(
                "Please confirm that document "
                "preparation is complete."
            )

        change_request_state(
            request_id=request_id,
            event="preparation_completed",
            actor=current_user,
            note=(
                "Document preparation manually confirmed "
                "as completed by the assigned Registrar."
            ),
            conditions={
                "preparation_complete": True
            }
        )

        return back_to_dashboard(
            "Document preparation completed. "
            "Request is now Ready for Release.",
            "success"
        )

    except ValueError as error:
        db.session.rollback()
        return back_to_dashboard(str(error))

    except Exception:
        db.session.rollback()
        raise


# ============================================
# ON HOLD / RESUME
# ============================================

@registrar_bp.route("/request/<int:request_id>/hold", methods=["POST"])
@login_required
@staff_required
def hold_request(request_id):
    try:
        document = get_preparation_request(request_id, require_owner=False)
        preparation = get_preparation(request_id)
        if preparation.status in (ACTIVE, PENDING):
            if preparation.preparing_registrar_id != current_user.id:
                raise ValueError("Only the preparing Registrar can place this request on hold.")
        elif preparation.status != QUEUED:
            raise ValueError("This request cannot be placed On Hold.")

        reason = (request.form.get("reason") or "").strip()
        if not reason:
            raise ValueError("Please provide a reason for On Hold.")

        change_request_state(
            request_id=request_id,
            event="hold_required",
            actor=current_user,
            note=reason,
            conditions={"hold_reason_provided": True},
        )
        return back_to_dashboard("Request placed On Hold.", "success")
    except ValueError as error:
        db.session.rollback()
        return back_to_dashboard(str(error))
    except Exception:
        db.session.rollback()
        raise


@registrar_bp.route("/request/<int:request_id>/resume", methods=["POST"])
@login_required
@staff_required
def resume_request(request_id):
    try:
        if not registrar_allowed():
            raise ValueError("Registrar access required.")
        document = (
            db.session.query(DocumentRequest)
            .filter(DocumentRequest.id == request_id)
            .with_for_update()
            .first()
        )
        if document is None or document.status != ON_HOLD:
            raise ValueError("Request is not On Hold.")
        preparation = get_preparation(request_id)
        if preparation.status == PENDING:
            if preparation.preparing_registrar_id != current_user.id:
                raise ValueError("Only the preparing Registrar can resume this pending request.")
        reason = (request.form.get("reason") or "").strip()
        if not reason:
            raise ValueError("Please confirm how the hold was resolved.")

        change_request_state(
            request_id=request_id,
            event="hold_resolved",
            actor=current_user,
            note=reason,
            conditions={"hold_resolved": True},
        )
        return back_to_dashboard("Hold resolved; request returned to Document Preparation.", "success")
    except ValueError as error:
        db.session.rollback()
        return back_to_dashboard(str(error))
    except Exception:
        db.session.rollback()
        raise
