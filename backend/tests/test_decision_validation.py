import pytest
from pydantic import ValidationError

from app.schemas.review import DecisionRequest


def test_decision_validation_accepts_valid_pairs() -> None:
    decision = DecisionRequest(
        group_id=1,
        image_id=2,
        state="keep",
        reason_code="count_matches",
        notes="ok",
    )
    assert decision.state == "keep"


def test_decision_validation_rejects_invalid_pairs() -> None:
    with pytest.raises(ValidationError):
        DecisionRequest(
            group_id=1,
            image_id=2,
            state="delete",
            reason_code="count_matches",
            notes="bad",
        )
