from enum import Enum


class Status(str, Enum):
    NEEDS_INFO = "needs_info"
    REJECTED = "rejected"
    VALID = "valid"


def determine_status(missing: list[str], invalid: list[str]) -> Status:
    if invalid:
        return Status.REJECTED
    if missing:
        return Status.NEEDS_INFO
    return Status.VALID