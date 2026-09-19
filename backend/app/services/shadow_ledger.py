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


def _last_json_record(path: Path) -> dict[str, object] | None:
    last_non_empty = ""
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                last_non_empty = line
    if not last_non_empty:
        return None
    try:
        value = json.loads(last_non_empty)
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None
