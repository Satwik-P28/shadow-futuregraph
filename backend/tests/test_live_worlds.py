import json

from shadow.benchmark.live_worlds import DOMAINS, STRUCTURES, generate_world, pilot_context


def test_thirty_worlds_are_frozen_and_heterogeneous():
    worlds = [generate_world(index) for index in range(30)]
    structures = [oracle["structure"] for _, oracle in worlds]
    assert set(structures) == set(STRUCTURES)
    assert all(structures.count(name) == 2 for name in STRUCTURES)
    assert {oracle["domain"] for _, oracle in worlds} == set(DOMAINS)
    for scenario, oracle in worlds:
        blob = json.dumps(pilot_context(scenario))
        assert "optimal" not in blob
        assert "minimal_cut" not in blob
        assert '"op"' not in blob
        again, again_oracle = generate_world(oracle["index"])
        assert scenario.model_dump() == again.model_dump()
        assert oracle["optimal"] == again_oracle["optimal"]
