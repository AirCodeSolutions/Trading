import json
from pathlib import Path

from app.domain.admission import AdmissionDecision
from app.domain.opportunity import PortfolioResearchResult


def save_research_admissions(
    path: Path,
    result: PortfolioResearchResult,
    *,
    merge: bool = False,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = (
        {
            strategy_id: decision.model_dump(mode="json")
            for strategy_id, decision in load_research_admissions(path).items()
        }
        if merge
        else {}
    )
    payload.update(
        {
            item.admission.strategy_id: item.admission.model_dump(mode="json")
            for item in result.results
        }
    )
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    temporary.replace(path)


def load_research_admissions(
    path: Path,
) -> dict[str, AdmissionDecision]:
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(payload, dict):
        return {}

    result: dict[str, AdmissionDecision] = {}
    for strategy_id, value in payload.items():
        try:
            result[str(strategy_id)] = AdmissionDecision.model_validate(value)
        except (TypeError, ValueError):
            continue
    return result
