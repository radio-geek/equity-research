"""ManagementStructured: narrative field and legacy rpt_and_gaps alias."""

from src.nodes.schemas import ManagementStructured

_PEOPLE = [{"name": "A", "designation": "MD", "description": "x"}]


def test_management_narrative_from_new_key() -> None:
    m = ManagementStructured.model_validate(
        {
            "people": _PEOPLE,
            "management_narrative": "Track record looks solid.",
        }
    )
    assert m.management_narrative == "Track record looks solid."


def test_management_narrative_from_legacy_rpt_key() -> None:
    m = ManagementStructured.model_validate(
        {
            "people": _PEOPLE,
            "rpt_and_gaps": "Legacy payload still parses.",
        }
    )
    assert m.management_narrative == "Legacy payload still parses."


def test_empty_narrative_defaults() -> None:
    m = ManagementStructured.model_validate({"people": _PEOPLE})
    assert m.management_narrative == ""
