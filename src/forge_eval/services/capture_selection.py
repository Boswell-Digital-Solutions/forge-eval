from __future__ import annotations

from typing import Any

from forge_eval.errors import StageError


def select_hidden_estimate(
    *,
    observed: int,
    chao1: dict[str, Any],
    chao2: dict[str, Any],
    ice: dict[str, Any],
    selection_policy: str,
    round_digits: int,
) -> dict[str, Any]:
    if selection_policy != "max_hidden":
        raise StageError(
            "unsupported capture selection policy",
            stage="capture_estimate",
            details={"capture_selection_policy": selection_policy},
        )
    if isinstance(observed, bool) or not isinstance(observed, int) or observed < 0:
        raise StageError(
            "selection observed count must be a non-negative integer",
            stage="capture_estimate",
            details={"observed": observed},
        )
    if (
        isinstance(round_digits, bool)
        or not isinstance(round_digits, int)
        or round_digits < 0
        or round_digits > 12
    ):
        raise StageError(
            "selection round_digits must be an integer in [0, 12]",
            stage="capture_estimate",
            details={"round_digits": round_digits},
        )

    candidates: list[tuple[str, float]] = []
    unavailable_estimators: list[str] = []

    chao1_hidden = _required_non_negative_number(chao1, "hidden")
    candidates.append(("chao1", chao1_hidden))

    ice_hidden = _required_non_negative_number(ice, "hidden")
    candidates.append(("ice", ice_hidden))

    if chao2.get("available") is True:
        chao2_hidden = chao2.get("hidden_estimate")
        if (
            isinstance(chao2_hidden, bool)
            or not isinstance(chao2_hidden, (int, float))
            or float(chao2_hidden) < 0.0
        ):
            raise StageError(
                "Chao2 available but hidden_estimate is invalid",
                stage="capture_estimate",
                details={"hidden_estimate": chao2_hidden},
            )
        candidates.append(("chao2", float(chao2_hidden)))
    else:
        unavailable_estimators.append("chao2")

    max_val = max(v for _, v in candidates)
    winners = [n for n, v in candidates if v == max_val]
    selected_source = winners[0] if len(winners) == 1 else "tie"
    selected_hidden = max_val

    return {
        "selection_policy": selection_policy,
        "selected_method": selection_policy,
        "selected_source": selected_source,
        "selected_hidden": _round_float(selected_hidden, round_digits),
        "selected_total": _round_float(observed + selected_hidden, round_digits),
        "unavailable_estimators": sorted(unavailable_estimators),
    }


def _required_non_negative_number(obj: dict[str, Any], key: str) -> float:
    value = obj.get(key)
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or float(value) < 0.0
    ):
        raise StageError(
            "selection input missing non-negative numeric field",
            stage="capture_estimate",
            details={"field": key, "value": value},
        )
    return float(value)


def _round_float(value: float, digits: int) -> float:
    return float(round(float(value), digits))
