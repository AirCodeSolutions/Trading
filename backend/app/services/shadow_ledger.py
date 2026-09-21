import json
from pathlib import Path

from app.domain.shadow import ShadowOpportunityDiagnostic


def append_shadow_observation(
    path: Path,
    diagnostic: ShadowOpportunityDiagnostic,
) -> bool:
    path.parent.mkdir(parents=True, exist_ok=True)
    identity = _identity(diagnostic)

    if path.is_file():
        last = _last_json_record(path)
        if last is not None and _record_identity(last) == identity:
            return False

    with path.open("a", encoding="utf-8") as handle:
        handle.write(diagnostic.model_dump_json())
        handle.write("\n")
    return True


def _identity(diagnostic: ShadowOpportunityDiagnostic) -> tuple[str, str, str]:
    return (
        diagnostic.symbol,
        diagnostic.mechanism.value,
        diagnostic.latest_closed_m5_at.isoformat(),
    )


def _record_identity(record: dict[str, object]) -> tuple[str, str, str] | None:
    try:
        return (
            str(record["symbol"]),
            str(record["mechanism"]),
            str(record["latest_closed_m5_at"]),
        )
    except KeyError:
        return None


def load_latest_shadow_observation(
    path: Path,
) -> ShadowOpportunityDiagnostic | None:
    record = _last_json_record(path)
    if record is None:
        return None
    try:
        return ShadowOpportunityDiagnostic.model_validate(record)
    except ValueError:
        return None


def _last_json_record(path: Path) -> dict[str, object] | None:
    if not path.is_file():
        return None
    with path.open(encoding="utf-8") as handle:
        lines = handle.readlines()
    for line in reversed(lines):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            return value
    return None
