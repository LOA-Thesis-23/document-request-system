from datetime import datetime, timezone

# (current_status, action) -> next_status. Mirrors Figure 3, plus the extra states
# outside the diagram: Submitted and Cancelled.
TRANSITIONS = {
    ('Submitted', 'mark_paid'): 'Payment Verification',
    ('Submitted', 'cancel'): 'Cancelled',

    ('Payment Verification', 'payment_verified'): 'Request Verification',
    ('Payment Verification', 'payment_correction_required'): 'For Correction',

    ('For Correction', 'corrected_payment_submitted'): 'Payment Verification',
    ('For Correction', 'corrected_information_submitted'): 'Request Verification',

    ('Request Verification', 'request_verified'): 'Document Preparation',
    ('Request Verification', 'request_correction_required'): 'For Correction',
    ('Request Verification', 'request_invalid'): 'Rejected',

    ('Document Preparation', 'exceptional_issue'): 'On Hold',
    ('On Hold', 'hold_resolved'): 'Document Preparation',
    ('Document Preparation', 'preparation_completed'): 'Ready for Release',

    ('Ready for Release', 'document_released'): 'Completed',   # will be triggered by the QR scan later
}

# Which staff role may trigger which action.
STAFF_ACTIONS = {
    'cashier': {'payment_verified', 'payment_correction_required'},
    'registrar': {'request_verified', 'request_correction_required', 'request_invalid',
                  'exceptional_issue', 'hold_resolved', 'preparation_completed'},
}

# Actions that must come with a written reason.
REASON_REQUIRED = {'payment_correction_required', 'request_correction_required', 'request_invalid'}


def apply_transition(doc_request, action, staff=None, student=None, note=None):
    """Validate (current_status, action) against TRANSITIONS, update, and log. Returns (ok, message)."""
    # Moved imports inside function to avoid circular import issues on app startup
    from app import db
    from app.models import StatusHistory

    from_status = doc_request.status
    to_status = TRANSITIONS.get((from_status, action))

    history = StatusHistory(
        document_request_id=doc_request.id,
        from_status=from_status,
        to_status=to_status or from_status,
        action=action,
        accepted=to_status is not None,
        staff_id=staff.id if staff else None,
        student_id=student.id if student else None,
        note=note,
    )
    db.session.add(history)

    if to_status is None:
        db.session.commit()
        return False, 'That status change is not allowed for this request.'

    doc_request.status = to_status
    if staff:
        doc_request.handled_by = staff.id
    if to_status == 'For Correction':
        doc_request.correction_from = from_status
        doc_request.correction_note = note
    if to_status == 'Rejected':
        doc_request.remarks = note
    if to_status == 'Completed':
        doc_request.date_completed = datetime.now(timezone.utc)

    db.session.commit()
    return True, f'Request moved to {to_status}.'