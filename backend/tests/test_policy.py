from shadow.policy.openshell import candidate_policy, compare_policy, load_boundary


def test_contained_policy_is_not_formally_verified_without_prover():
    boundary = load_boundary()
    result = compare_policy(candidate_policy(["api.tokenfactory.nebius.com"]), boundary)
    assert result["structural_status"] == "within_boundary"
    assert result["prover_status"] == "prover_unavailable"
    assert result["formally_verified"] is False
    assert result["display"] != "FORMALLY VERIFIED"


def test_overbroad_policy():
    result = compare_policy(candidate_policy(["evil.example"]))
    assert result["structural_status"] == "outside_boundary"
    assert result["formally_verified"] is False


def test_unsupported_shape():
    result = compare_policy({"network": {"allow": []}})
    assert result["structural_status"] == "unsupported"
    assert result["formally_verified"] is False
