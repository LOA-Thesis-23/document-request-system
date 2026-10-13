

from flask import (
    Blueprint,
    redirect,
    url_for,
    flash,
    request,
    abort,
    current_app,
    Response,
)
from flask_login import login_required, current_user

from app import db
from app.decorators import staff_required
from app.models import DocumentRequest
from app.services.lifecycle_service import change_request_state
from app.algorithms.lifecycle import PAYMENT_VERIFICATION


cashier_bp = Blueprint(
    "cashier",
    __name__,
    url_prefix="/cashier"
)


def cashier_only():
    return (
        current_user.role == "cashier"
        and not current_user.is_disabled
    )


def receipt_path(doc_request):
    # New requests store the private bucket object path in or_photo_path.
    path = doc_request.or_photo_path
    if not path or path.startswith('/') or '..' in path.split('/'):
        return None
    return path


@cashier_bp.route(
    "/request/<int:request_id>/receipt",
    methods=["GET"]
)
@login_required
@staff_required
def view_receipt(request_id):
    if not cashier_only():
        abort(403)

    doc_request = DocumentRequest.query.get_or_404(
        request_id
    )

    path = receipt_path(doc_request)
    if path is None:
        abort(404)

    try:
        content = get_receipt(path)
    except ReceiptStorageError:
        current_app.logger.exception('Receipt retrieval failed for request %s', request_id)
        abort(502)
    if content is None:
        abort(404)

    extension = path.rsplit('.', 1)[-1].lower()
    mime = {
        'jpg': 'image/jpeg', 'jpeg': 'image/jpeg',
        'png': 'image/png', 'pdf': 'application/pdf',
    }.get(extension, 'application/octet-stream')
    return Response(content, mimetype=mime, headers={
        'Content-Disposition': 'inline',
        'Cache-Control': 'private, no-store',
        'X-Content-Type-Options': 'nosniff',
    })



@cashier_bp.route(
    "/request/<int:request_id>/accept",
    methods=["POST"]
)
@login_required
@staff_required
def accept_request(request_id):
    if not cashier_only():
        abort(403)

    doc_request = DocumentRequest.query.get_or_404(
        request_id
    )

    if doc_request.status != PAYMENT_VERIFICATION:
        flash(
            "This request is not awaiting payment verification."
        )
        return redirect(url_for("staff.home"))

    path = receipt_path(doc_request)
    if path is None:
        flash("Cannot approve: no receipt is attached.")
        return redirect(url_for("staff.home"))
    try:
        if get_receipt(path) is None:
            flash("Cannot approve: receipt is missing from storage.")
            return redirect(url_for("staff.home"))
    except ReceiptStorageError:
        current_app.logger.exception('Receipt check failed for request %s', request_id)
        flash("Cannot verify receipt storage right now. Please retry.")
        return redirect(url_for("staff.home"))

    or_number = request.form.get(
        "or_number", ""
    ).strip()

    if not or_number:
        flash("Official Receipt number is required.")
        return redirect(url_for("staff.home"))

    if len(or_number) > 100:
        flash("OR number must not exceed 100 characters.")
        return redirect(url_for("staff.home"))

    if request.form.get("confirm_payment") != "yes":
        flash("Please confirm that you reviewed the receipt.")
        return redirect(url_for("staff.home"))

    try:
        # Set the OR number in the current transaction.
        doc_request.or_number = or_number

        # The lifecycle service commits the transition.
        # The OR number is saved in that same transaction.
        change_request_state(
            request_id=request_id,
            event="payment_verified",
            actor=current_user,
            note=(
                "Payment manually verified by cashier. "
                f"Official Receipt No.: {or_number}"
            ),
            conditions={
                "payment_verified": True
            }
        )

        flash(
            "Payment verified. OR number saved. "
            "Request forwarded to Registrar."
        )

    except ValueError as error:
        db.session.rollback()
        flash(str(error))

    except Exception:
        db.session.rollback()
        current_app.logger.exception(
            "Failed to approve payment for request %s",
            request_id
        )
        flash("Unable to approve payment. Please try again.")

    return redirect(url_for("staff.home"))
