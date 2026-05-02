import json
import pytest
from pathlib import Path


@pytest.fixture(scope="session")
def policy():
    policy_path = Path(__file__).parent.parent.parent / "policy_terms.json"
    with open(policy_path) as f:
        return json.load(f)


@pytest.fixture(scope="session")
def test_cases():
    tc_path = Path(__file__).parent.parent.parent / "test_cases.json"
    with open(tc_path) as f:
        return json.load(f)["test_cases"]
