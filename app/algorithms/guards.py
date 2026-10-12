
GUARDS = {
    "payment_verified": "payment_verified",
    "request_verified": "request_valid",
    "preparation_completed": "preparation_complete",
    "document_released": "release_verified",
    "correction_submitted": "correction_resolved",
    "hold_resolved": "hold_resolved"
}


def check_guard(event, context):
    required = GUARDS.get(event)

    if required is None:
        return True

    return context.get(required) is True
