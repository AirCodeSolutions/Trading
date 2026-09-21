from pathlib import Path

from app.domain.opportunity import OpportunityMechanism
from app.services.blocked_probe_registry import _parse_state_name as parse_probe_state
from app.services.paper_registry import _parse_state_name as parse_paper_state


def test_paper_registry_parses_directional_pullback_slug() -> None:
    parsed = parse_paper_state(
        Path("GBPUSD_directional_pullback_paper_state.json")
    )

    assert parsed == (
        "GBPUSD",
        OpportunityMechanism.DIRECTIONAL_PULLBACK_RESUMPTION,
        "GBPUSD_directional_pullback",
    )


def test_blocked_probe_registry_parses_directional_pullback_slug() -> None:
    parsed = parse_probe_state(
        Path("GBPUSD_directional_pullback_blocked_probe_state.json")
    )

    assert parsed == (
        "GBPUSD",
        OpportunityMechanism.DIRECTIONAL_PULLBACK_RESUMPTION,
        "GBPUSD_directional_pullback",
    )
