from datetime import datetime, timezone
from dataclasses import dataclass
from math import isfinite

from app.models import (
    DocumentRequest,
    PreparationQueue,
    PreparationActivity,
)


DOCUMENT_PREPARATION = "Document Preparation"
QUEUED = "Queued"

MINIMUM_EPT_MINUTES = 1.0


@dataclass
class HRRNResult:
    request_id: int
    document_type_id: int
    waiting_time: float
    original_ept: float
    actual_preparation_time: float
    remaining_ept: float
    response_ratio: float
    queue_entered_at: datetime
    rank: int = 0


def normalize_datetime(value):
    """
    Convert datetime to naive UTC for consistent
    calculations with database timestamps.
    """
    if value is None:
        raise ValueError("Timestamp is required.")

    if value.tzinfo is not None:
        return value.astimezone(
            timezone.utc
        ).replace(tzinfo=None)

    return value


def current_utc():
    return datetime.now(timezone.utc).replace(
        tzinfo=None
    )


def calculate_waiting_time(
    queue_entered_at,
    current_time=None
):
    """
    WT = Current Time - Queue Entry Time

    Waiting time resets whenever a request
    is requeued.
    """
    now = normalize_datetime(
        current_time or current_utc()
    )

    entered = normalize_datetime(queue_entered_at)

    seconds = (now - entered).total_seconds()

    return max(0.0, seconds / 60.0)


def calculate_actual_preparation_time(activities):
    """
    APT = Sum of completed active preparation intervals.

    Excludes:
    - Queue waiting time
    - Pending Dependencies
    - On Hold time

    Open intervals are not counted until closed.
    """
    total_seconds = 0.0

    for activity in activities:
        if activity.ended_at is None:
            continue

        started = normalize_datetime(
            activity.started_at
        )

        ended = normalize_datetime(
            activity.ended_at
        )

        seconds = (ended - started).total_seconds()

        if seconds > 0:
            total_seconds += seconds

    return total_seconds / 60.0


def calculate_remaining_ept(
    original_ept,
    actual_preparation_time
):
    """
    Remaining EPT = Original EPT - Accumulated APT

    Minimum remaining EPT = 1 minute.
    """
    original_ept = float(original_ept)
    actual_preparation_time = float(
        actual_preparation_time
    )

    if not isfinite(original_ept) or original_ept <= 0:
        raise ValueError(
            "Original EPT must be positive and finite."
        )

    if (
        not isfinite(actual_preparation_time)
        or actual_preparation_time < 0
    ):
        raise ValueError(
            "APT must be nonnegative and finite."
        )

    return max(
        MINIMUM_EPT_MINUTES,
        original_ept - actual_preparation_time
    )


def calculate_response_ratio(
    waiting_time,
    estimated_preparation_time
):
    """
    HRRN Formula:

        RR = (WT + EPT) / EPT

    Higher RR means higher scheduling priority.
    """
    waiting_time = float(waiting_time)
    estimated_preparation_time = float(
        estimated_preparation_time
    )

    if not isfinite(waiting_time) or waiting_time < 0:
        raise ValueError(
            "Waiting time must be nonnegative and finite."
        )

    if (
        not isfinite(estimated_preparation_time)
        or estimated_preparation_time <= 0
    ):
        raise ValueError(
            "EPT must be positive and finite."
        )

    return (
        waiting_time + estimated_preparation_time
    ) / estimated_preparation_time


def get_eligible_requests():
    """
    Only include requests with:

    FSM state = Document Preparation
    Internal status = Queued
    """
    return (
        PreparationQueue.query
        .join(
            DocumentRequest,
            PreparationQueue.document_request_id
            == DocumentRequest.id
        )
        .filter(
            DocumentRequest.status
            == DOCUMENT_PREPARATION,
            PreparationQueue.status == QUEUED
        )
        .order_by(
            PreparationQueue.queue_entered_at.asc(),
            PreparationQueue.id.asc()
        )
        .all()
    )


def calculate_hrrn_schedule(current_time=None):
    """
    Calculate and rank all eligible requests.

    Sorting:
    1. Highest response ratio
    2. Earliest queue-entry timestamp
    3. Lowest request ID

    Recalculate when a scheduling decision is needed.
    """
    now = normalize_datetime(
        current_time or current_utc()
    )

    eligible = get_eligible_requests()

    results = []

    for preparation in eligible:
        document = preparation.document_request

        activities = PreparationActivity.query.filter_by(
            document_request_id=document.id
        ).all()

        waiting_time = calculate_waiting_time(
            preparation.queue_entered_at,
            now
        )

        actual_time = calculate_actual_preparation_time(
            activities
        )

        remaining_ept = calculate_remaining_ept(
            preparation.original_ept_minutes,
            actual_time
        )

        ratio = calculate_response_ratio(
            waiting_time,
            remaining_ept
        )

        result = HRRNResult(
            request_id=document.id,
            document_type_id=document.document_type_id,
            waiting_time=waiting_time,
            original_ept=preparation.original_ept_minutes,
            actual_preparation_time=actual_time,
            remaining_ept=remaining_ept,
            response_ratio=ratio,
            queue_entered_at=preparation.queue_entered_at
        )

        results.append(result)

    results.sort(
        key=lambda item: (
            -item.response_ratio,
            normalize_datetime(item.queue_entered_at),
            item.request_id
        )
    )

    for index, result in enumerate(results, start=1):
        result.rank = index

    return results


def get_next_request(current_time=None):
    """
    Return the highest-priority eligible request.

    Returns None when the queue is empty.
    """
    schedule = calculate_hrrn_schedule(
        current_time=current_time
    )

    if not schedule:
        return None

    return schedule[0]


def get_request_priority(request_id, current_time=None):
    """
    Return HRRN information for a specific
    queued request.
    """
    schedule = calculate_hrrn_schedule(
        current_time=current_time
    )

    for result in schedule:
        if result.request_id == request_id:
            return result

    return None
