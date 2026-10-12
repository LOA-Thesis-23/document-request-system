EVENT_PERMISSIONS = {
    "payment_verified": ["cashier"],
    "request_verified": ["registrar"],
    "preparation_completed": ["registrar"],
    "document_released": ["registrar"],
    "correction_required": ["cashier", "registrar"],
    "correction_submitted": ["student"],
    "hold_required": ["registrar"],
    "hold_resolved": ["registrar"],
    "request_rejected": ["cashier", "registrar"]
}


def check_permission(event, role):
    allowed_roles = EVENT_PERMISSIONS.get(event, [])
    return role in allowed_roles
