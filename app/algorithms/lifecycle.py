# 1. Lifecycle states
PAYMENT_VERIFICATION = "Payment Verification"
REQUEST_VERIFICATION = "Request Verification"
DOCUMENT_PREPARATION = "Document Preparation"
READY_FOR_RELEASE = "Ready for Release"
COMPLETED = "Completed"

FOR_CORRECTION = "For Correction"
ON_HOLD = "On Hold"
REJECTED = "Rejected"

INITIAL_STATE = PAYMENT_VERIFICATION
TERMINAL_STATES = {COMPLETED, REJECTED}

# 2. Transition rules
# Each state defines its permitted events and next states.
TRANSITIONS = {
    PAYMENT_VERIFICATION: {
        "payment_verified": REQUEST_VERIFICATION,
        "correction_required": FOR_CORRECTION,
        "request_rejected": REJECTED
    },

    REQUEST_VERIFICATION: {
        "request_verified": DOCUMENT_PREPARATION,
        "correction_required": FOR_CORRECTION,
        "request_rejected": REJECTED
    },

    DOCUMENT_PREPARATION: {
        "preparation_completed": READY_FOR_RELEASE,
        "hold_required": ON_HOLD
    },

    READY_FOR_RELEASE: {
        "document_released": COMPLETED
    },

    FOR_CORRECTION: {
        "correction_submitted": None
    },

    ON_HOLD: {
        "hold_resolved": DOCUMENT_PREPARATION
    },

    COMPLETED: {},
    REJECTED: {}
}

# 3. Guard conditions
GUARDS = {
    "payment_verified": "payment_verified",
    "request_verified": "request_valid",
    "preparation_completed": "preparation_complete",
    "document_released": "release_verified",
    "correction_submitted": "correction_resolved",
    "hold_resolved": "hold_resolved"
}

# 4. Role permissions
PERMISSIONS = {
    "payment_verified": {"cashier"},
    "request_verified": {"registrar"},
    "preparation_completed": {"registrar"},
    "document_released": {"registrar"},
    "correction_required": {"cashier", "registrar"},
    "correction_submitted": {"student"},
    "hold_required": {"registrar"},
    "hold_resolved": {"registrar"},
    "request_rejected": {"cashier", "registrar"}
}


# 5. Guard validation
def check_guard(event, context):
    required = GUARDS.get(event)

    if required is None:
        return True

    return context.get(required) is True

# 6. Role authorization
def check_permission(event, role):
    return role in PERMISSIONS.get(event, set())

# 7. Main FSM transition function
def transition(current_state, event, context=None, role=None):
    context = context or {}

    # Check whether the current state exists
    if current_state not in TRANSITIONS:
        raise ValueError("Unknown lifecycle state.")

    # Check whether the event is permitted in this state
    if event not in TRANSITIONS[current_state]:
        raise ValueError(
            f"Event '{event}' is not allowed "
            f"in state '{current_state}'."
        )

    # Check role authorization
    if not check_permission(event, role):
        raise ValueError(
            f"Role '{role}' is not authorized "
            f"for event '{event}'."
        )

    # Check guard conditions
    if not check_guard(event, context):
        raise ValueError(
            f"Guard condition not satisfied: {event}"
        )

    # Determine next state
    next_state = TRANSITIONS[current_state][event]

    # Return to the originating verification state
    if event == "correction_submitted":
        next_state = context.get("correction_from")

        if next_state not in {
            PAYMENT_VERIFICATION,
            REQUEST_VERIFICATION
        }:
            raise ValueError(
                "Invalid correction origin."
            )
    return next_state

# 8. Utility functions
def get_allowed_events(current_state):
    return list(TRANSITIONS.get(current_state, {}).keys())

def is_terminal(current_state):
    return current_state in TERMINAL_STATES
