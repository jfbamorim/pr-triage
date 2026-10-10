from enum import Enum


class Band(str, Enum):
    NO_BLOCKERS = "no_blockers"
    POLICY_TO_BE_VERIFIED = "policy_to_be_verified"
    HUMAN_ACTION = "human_action"


def determine_band(estimated_value_eur: float) -> Band:
    if estimated_value_eur < 1000:
        return Band.NO_BLOCKERS
    if estimated_value_eur <= 5000:
        return Band.POLICY_TO_BE_VERIFIED
    return Band.HUMAN_ACTION