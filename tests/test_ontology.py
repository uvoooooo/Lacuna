"""Tests for the TOML-backed ontology loader."""

import pytest

from narrative_audit.graph import GapImportance
from narrative_audit.ontology import (
    DEFAULT_ONTOLOGY,
    GENERIC_ROLES,
    OntologyError,
    load_ontology,
    match_event_type,
    parse_ontology,
)

_CUSTOM = """
[[event_types]]
name = "claim_filing"
label_zh = "报案/索赔"
keywords = ["报案", "索赔"]

[[event_types.roles]]
name = "claimant"
label_zh = "索赔人"
importance = "required"
question = "是谁提出的索赔？"

[[event_types.roles]]
name = "policy"
label_zh = "保单信息"
importance = "expected"
question = "涉及哪份保单？"
"""


def test_builtin_ontology_loads_from_package_data():
    assert set(DEFAULT_ONTOLOGY) == {"dismissal", "dispute", "accusation", "harm", "agreement"}
    dismissal = DEFAULT_ONTOLOGY["dismissal"]
    assert dismissal.label_zh == "解雇/开除"
    assert "开除" in dismissal.keywords
    assert {r.name for r in dismissal.required_roles()} == {
        "employer",
        "reason",
        "prior_employment",
    }
    assert all(r.question for et in DEFAULT_ONTOLOGY.values() for r in et.roles)
    assert {r.name for r in GENERIC_ROLES} == {"cause", "time_place"}


def test_load_custom_ontology(tmp_path):
    path = tmp_path / "insurance.toml"
    path.write_text(_CUSTOM, encoding="utf-8")

    ontology = load_ontology(path)
    assert set(ontology) == {"claim_filing"}
    et = ontology["claim_filing"]
    assert [r.name for r in et.required_roles()] == ["claimant"]
    assert et.roles[1].importance == GapImportance.EXPECTED

    # The custom catalogue drives keyword typing instead of the default one.
    assert match_event_type("我上周报案了", ontology).name == "claim_filing"
    assert match_event_type("上周五我被开除了", ontology) is None


def test_custom_ontology_drives_gap_detection(tmp_path):
    from narrative_audit.agents import GapDetectorAgent
    from narrative_audit.graph import GraphNode
    from narrative_audit.state import AuditState

    path = tmp_path / "insurance.toml"
    path.write_text(_CUSTOM, encoding="utf-8")

    state = AuditState(text="我上周报案了")
    state.graph.add_node(
        GraphNode(id="ev1", label="报案", node_type="event", event_type="claim_filing")
    )
    GapDetectorAgent(ontology=load_ontology(path)).run(state)
    assert {g.role for g in state.gaps} == {"claimant", "policy"}


def test_pipeline_from_config_uses_custom_ontology(tmp_path):
    from narrative_audit.agents import GapDetectorAgent, OntologyReasonerAgent
    from narrative_audit.config import pipeline_from_config

    path = tmp_path / "insurance.toml"
    path.write_text(_CUSTOM, encoding="utf-8")

    pipeline = pipeline_from_config({"ontology": {"path": str(path)}})
    reasoner = next(a for a in pipeline.agents if isinstance(a, OntologyReasonerAgent))
    gap_detector = next(a for a in pipeline.agents if isinstance(a, GapDetectorAgent))
    assert set(reasoner.ontology) == {"claim_filing"}
    assert set(gap_detector.ontology) == {"claim_filing"}


@pytest.mark.parametrize(
    "data",
    [
        {},  # no event types at all
        {"event_types": [{"label_zh": "缺名字"}]},  # missing name
        {"event_types": [{"name": "a"}, {"name": "a"}]},  # duplicate name
        {"event_types": [{"name": "a", "keywords": "notalist"}]},  # bad keywords
        {  # bad importance
            "event_types": [
                {"name": "a", "roles": [{"name": "r", "importance": "critical"}]},
            ]
        },
    ],
)
def test_parse_ontology_rejects_bad_schema(data):
    with pytest.raises(OntologyError):
        parse_ontology(data)
