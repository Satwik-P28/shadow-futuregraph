"""Freeform plans stay honest unless an example context is explicit."""

from fastapi.testclient import TestClient

from shadow.api.app import create_app

TRIP = "Move my NYC trip to Friday and make sure everything still works."
DENTIST = "Move my dentist appointment to Thursday without interfering with class."


def _client() -> TestClient:
    return TestClient(create_app())


def test_freeform_keeps_the_exact_text() -> None:
    text = f"  {TRIP} Extra note."
    body = _client().post("/api/plans/freeform", json={"text": text, "demo_context_id": "travel"}).json()
    assert body["plan"]["text"] == text
    assert body["plan"]["scenario_id"] == "travel"
    assert body["modelability"]["status"] == "SUPPORTED"


def test_supported_example_routes_through_the_world_compiler() -> None:
    body = _client().post("/api/plans/freeform", json={"text": TRIP, "demo_context_id": "travel"}).json()
    assert body["modelability"]["status"] == "SUPPORTED"
    assert "world compiler" in body["modelability"]["provenance"]
    assert body["modelability"]["compiled_constraints"]
    assert body["modelability"]["selected_skill"] == "Reschedule Trip"
    assert body["plan"]["recommended_repair_id"] == "b1120"
    assert body["plan"]["compiled_from"] == "calendar, email, reservation, preferences"


def test_missing_structure_asks_instead_of_inventing_a_world() -> None:
    body = _client().post("/api/plans/freeform", json={"text": DENTIST}).json()
    assert body["plan"] is None
    assert body["modelability"]["status"] == "NEEDS_INFORMATION"
    assert body["modelability"]["selected_skill"] == "Coordinate Schedule"
    assert any("calendar" in item for item in body["modelability"]["missing_information"])
    assert "b1120" not in str(body)


def test_unsupported_request_does_not_build_a_future() -> None:
    body = _client().post("/api/plans/freeform", json={"text": "Should I marry this person?"}).json()
    assert body["plan"] is None
    assert body["modelability"]["status"] == "UNSUPPORTED"
    assert body["modelability"]["selected_skill"] is None
    assert "grounded information" in body["modelability"]["reason"]
    assert body["modelability"]["missing_information"] == []


def test_trip_wording_does_not_silently_select_the_demo() -> None:
    body = _client().post("/api/plans/freeform", json={"text": TRIP}).json()
    assert body["plan"] is None
    assert body["modelability"]["status"] == "NEEDS_INFORMATION"
    assert "example context" not in body["modelability"]["provenance"]
    assert body["modelability"]["selected_skill"] == "Reschedule Trip"


def test_explicit_apartment_example_uses_that_context() -> None:
    text = "I'm thinking about moving apartments next month. Does this plan actually work?"
    body = _client().post("/api/plans/freeform", json={"text": text, "demo_context_id": "apartment"}).json()
    assert body["plan"]["scenario_id"] == "apartment"
    assert body["plan"]["text"] == text
    assert body["plan"]["recommended_repair_id"]
    assert body["modelability"]["status"] == "SUPPORTED"


def test_trip_without_a_day_names_that_gap() -> None:
    body = _client().post("/api/plans/freeform", json={"text": "Move my NYC trip."}).json()
    assert body["plan"] is None
    assert "which day you want to travel" in body["modelability"]["missing_information"]


def test_disruption_without_records_needs_information() -> None:
    body = _client().post("/api/plans/freeform", json={"text": "The fare changed."}).json()
    assert body["plan"] is None
    assert body["modelability"]["status"] == "NEEDS_INFORMATION"
    assert body["modelability"]["selected_skill"] == "Handle Trip Disruption"


def test_unstructured_request_is_unsupported() -> None:
    body = _client().post("/api/plans/freeform", json={"text": "What color should the bike be?"}).json()
    assert body["plan"] is None
    assert body["modelability"]["status"] == "UNSUPPORTED"


def test_schedule_without_a_day_names_the_gaps() -> None:
    body = _client().post("/api/plans/freeform", json={"text": "Move the meeting."}).json()
    missing = body["modelability"]["missing_information"]
    assert body["modelability"]["status"] == "NEEDS_INFORMATION"
    assert "which day the event should move to" in missing
    assert "which commitments must stay where they are" in missing


def test_blank_plan_is_rejected() -> None:
    response = _client().post("/api/plans/freeform", json={"text": "   "})
    assert response.status_code == 400
    assert "Enter what you are planning" in response.json()["detail"]
