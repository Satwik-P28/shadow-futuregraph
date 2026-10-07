"""Grounding tests. These proposals are handwritten stand-ins for a model, not live calls."""

from shadow.repair.evaluate import evaluate_repairs
from shadow.simulation.engine import bind, evaluate_constraints
from shadow.world.loader import effects_for
from shadow.world.semantic import SemanticWorld, coerce_semantic, ground_semantic

TRAIN = (
    "My class ends at 3:30. The drive to the station takes 15-35 minutes, "
    "the train leaves at 4:10, and parking takes another 5-12 minutes."
)


def test_composed_ranges_fail_only_at_the_high_end() -> None:
    world = SemanticWorld.model_validate(
        {
            "facts": [
                {"id": "class_end", "name": "class end", "quote": "class ends at 3:30", "value": "3:30"},
                {"id": "parking", "name": "parking", "quote": "parking takes another 5-12 minutes", "value": "5-12 minutes"},
                {"id": "drive", "name": "drive", "quote": "drive to the station takes 15-35 minutes", "value": "15-35 minutes"},
                {"id": "train", "name": "train", "quote": "train leaves at 4:10", "value": "4:10"},
            ],
            "links": [{"id": "catch", "relation": "sum_before", "inputs": ["class_end", "parking", "drive"], "deadline": "train"}],
        }
    )
    grounded = ground_semantic(world, [{"id": "user", "text": TRAIN}])
    assert grounded.status == "EXECUTABLE"
    assert grounded.scenario is not None
    low = bind(grounded.scenario, {}, {})
    assert evaluate_constraints(grounded.scenario, low)["c_catch"] is True
    high = {
        "parking_span": 12.0,
        "drive_span": 35.0,
    }
    assert evaluate_constraints(grounded.scenario, bind(grounded.scenario, {}, high))["c_catch"] is False
    scored = evaluate_repairs(
        grounded.scenario,
        [(item.id, item.label, item.action_ids, "catalog") for item in grounded.scenario.bundles],
        seed=3,
    )
    keep = next(item for item in scored if item.id == "keep")
    assert keep.failures


def test_missing_transfer_is_not_invented() -> None:
    text = "I have to get to a wedding by 5, and my train arrives at 4:15."
    world = SemanticWorld.model_validate(
        {
            "facts": [
                {"id": "train", "name": "train", "quote": "train arrives at 4:15", "value": "4:15"},
                {"id": "wedding", "name": "wedding", "quote": "wedding by 5", "value": "5"},
            ],
            "links": [{"id": "arrive", "relation": "sum_before", "inputs": ["train"], "deadline": "wedding"}],
            "unknowns": ["transfer from the station to the wedding"],
        }
    )
    grounded = ground_semantic(world, [{"id": "user", "text": text}])
    assert grounded.status == "PARTIALLY_EXECUTABLE"
    assert any("transfer" in item for item in grounded.missing)
    assert grounded.scenario is not None
    labels = " ".join(var.label for var in grounded.scenario.variables)
    assert "20" not in labels


def test_unconfirmed_time_and_conflict_do_not_become_a_deadline() -> None:
    vague = ground_semantic(
        SemanticWorld.model_validate(
            {"facts": [{"id": "dinner", "name": "dinner", "quote": "dinner around seven", "value": "around seven"}]}
        ),
        [{"id": "user", "text": "My friend wants dinner around seven, but she hasn't confirmed the reservation."}],
    )
    assert vague.status == "NEEDS_INFORMATION"
    assert vague.scenario is None
    conflict = ground_semantic(
        SemanticWorld.model_validate(
            {
                "facts": [
                    {"id": "a", "name": "interview", "quote": "interview is at 2", "value": "2"},
                    {"id": "b", "name": "interview", "quote": "email says 3", "value": "3"},
                ]
            }
        ),
        [{"id": "user", "text": "My calendar says the interview is at 2, but the recruiter's newer email says 3."}],
    )
    assert conflict.status == "CONTRADICTORY"


def test_optional_spend_can_be_dropped_and_overlap_fails() -> None:
    budget = ground_semantic(
        SemanticWorld.model_validate(
            {
                "facts": [
                    {"id": "cap", "name": "discretionary", "quote": "$450 left", "value": "$450"},
                    {"id": "gift", "name": "birthday", "quote": "committed $180", "value": "$180"},
                    {"id": "phones", "name": "headphones", "quote": "considering buying headphones for $210", "value": "$210"},
                    {"id": "tickets", "name": "tickets", "quote": "concert tickets for $125", "value": "$125"},
                ],
                "links": [{"relation": "sum_at_most", "inputs": ["gift", "phones", "tickets"], "deadline": "cap"}],
            }
        ),
        [{"id": "user", "text": "I've got $450 left. I already committed $180 to a birthday present. I'm considering buying headphones for $210 and concert tickets for $125."}],
    )
    assert budget.scenario is not None
    assert evaluate_constraints(budget.scenario, bind(budget.scenario, {}, {}))["c_budget"] is False
    dropped = effects_for(budget.scenario, ["drop_headphones"])
    assert evaluate_constraints(budget.scenario, bind(budget.scenario, dropped, {}))["c_budget"] is True
    overlap = ground_semantic(
        SemanticWorld.model_validate(
            {
                "facts": [
                    {"id": "car", "name": "car", "quote": "from 3 until 6", "value": "from 3 until 6"},
                    {"id": "airport", "name": "airport", "quote": "at 4", "value": "at 4"},
                ],
                "links": [{"id": "car", "relation": "overlaps", "inputs": ["car", "airport"]}],
            }
        ),
        [{"id": "user", "text": "My partner needs the car from 3 until 6. I was planning to drive to the airport at 4."}],
    )
    assert overlap.scenario is not None
    assert evaluate_constraints(overlap.scenario, bind(overlap.scenario, {}, {}))["c_car"] is False


def test_quarter_past_and_spoken_ranges_parse() -> None:
    from shadow.world.semantic import _read

    quarter = _read("quarter past four")
    assert quarter is not None and quarter["point"] == 16 * 60 + 15
    spoken = _read("twenty minutes to fifty")
    assert spoken is not None and spoken["low"] == 20 and spoken["high"] == 50
    assert _read("at five")["point"] == 17 * 60
    assert _read("around seven")["unknown"] is True
    assert _read("about half an hour")["point"] == 30


def test_a_link_quote_with_an_ellipsis_still_evaluates() -> None:
    world = SemanticWorld.model_validate(
        {
            "facts": [
                {"id": "class_end", "name": "class end", "quote": "class ends at 3:30", "value": "3:30"},
                {"id": "drive_to_station", "name": "drive", "quote": "takes 15-35 minutes", "value": "15-35 minutes"},
                {"id": "parking_time", "name": "parking", "quote": "parking takes another 5-12 minutes", "value": "5-12 minutes"},
                {"id": "train_leaves", "name": "train", "quote": "train leaves at 4:10", "value": "4:10"},
            ],
            "links": [
                {
                    "relation": "sum_before",
                    "inputs": ["class_end", "drive_to_station", "parking_time"],
                    "deadline": "train_leaves",
                    "hardness": "soft",
                    "quote": "drive takes 15-35 minutes, ... parking takes another 5-12 minutes",
                }
            ],
        }
    )
    grounded = ground_semantic(world, [{"id": "user", "text": TRAIN}])
    assert grounded.status == "EXECUTABLE"
    assert grounded.scenario is not None
    assert grounded.scenario.constraints[0].hardness == "hard"


def test_invented_quote_is_rejected_and_aliases_coerce() -> None:
    grounded = ground_semantic(
        SemanticWorld.model_validate(
            {"facts": [{"id": "x", "name": "exit", "quote": "takes 12 minutes", "value": "12 minutes"}]}
        ),
        [{"id": "user", "text": "The walk is short."}],
    )
    assert grounded.status == "INVALID_MODEL_OUTPUT"
    coerced = coerce_semantic({"variables": [{"name": "doors", "value": "1:40 PM", "quote": "Doors close at 1:40 PM"}]})
    assert coerced["facts"][0]["id"] == "doors"
    assert coerced["facts"][0]["value"] == "1:40 PM"
