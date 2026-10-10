from enum import Enum


class Status(str, Enum):
    NEEDS_INFO = "needs_info"
    REJECTED = "rejected"
    VALID = "valid"


class Reason(str, Enum):
    INVALID_DATA = "invalid_data"
    SUSPICIOUS_ACTIVITY = "suspicious_activity"


def determine_status(missing: list[str], invalid: list[str]) -> Status:
    if invalid:
        return Status.REJECTED
    if missing:
        return Status.NEEDS_INFO
    return Status.VALID