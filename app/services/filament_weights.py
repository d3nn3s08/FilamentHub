from typing import Optional, Tuple

from app.models.material import Material
from app.models.spool import Spool


def compute_remaining_weight(
    weight_current: Optional[float],
    weight_empty: Optional[float],
    *,
    is_bambu: bool,
) -> Optional[float]:
    """
    Robust remaining-weight calculation.

    `weight_current` can be either:
      - the gross scale value (spule + filament), or
      - the net filament weight (filament only) for manual entries.

    Strategy:
      - For Bambu materials the device reports filament-only, so return that.
      - For non-Bambu: if `weight_current` looks like net filament (e.g. close
        to total expected filament), use it directly. Otherwise assume it's a
        gross measurement and subtract `weight_empty`.
    """
    if weight_current is None:
        return None
    try:
        current = float(weight_current)
    except Exception:
        return None
    if is_bambu:
        return max(0.0, current)
    if weight_empty is None:
        # Without empty weight we cannot convert gross->net reliably; assume
        # provided value is already net filament.
        return max(0.0, current)
    try:
        empty = float(weight_empty)
    except Exception:
        return max(0.0, current)

    # If current - empty is small (<=50g) we assume `current` already is net
    # filament and return it directly. This handles the case where
    # normalisation has already stored net filament values.
    if current - empty <= 50:
        return max(0.0, current)

    # Otherwise assume `current` is a gross (spool+filament) measurement
    # and subtract the empty spool weight.
    return max(0.0, current - empty)


def compute_total_weight(weight_full: Optional[float], weight_empty: Optional[float]) -> Optional[float]:
    if weight_full is None or weight_empty is None:
        return None
    try:
        total = float(weight_full) - float(weight_empty)
    except Exception:
        return None
    return max(0.0, total)


def compute_remaining_percent(
    remaining_g: Optional[float],
    total_g: Optional[float],
) -> Optional[float]:
    if remaining_g is None or total_g is None or total_g <= 0:
        return None
    try:
        percent = (float(remaining_g) / float(total_g)) * 100.0
    except Exception:
        return None
    return max(0.0, min(100.0, round(percent, 1)))


def compute_spool_remaining(
    spool: Spool,
    material: Optional[Material],
) -> Tuple[Optional[float], Optional[float], Optional[float]]:
    is_bambu = bool(material and material.is_bambu is True)

    # Determine total filament capacity (net filament) using material or spool values
    if is_bambu and material:
        total = compute_total_weight(material.spool_weight_full, material.spool_weight_empty)
    else:
        total = compute_total_weight(spool.weight_full, spool.weight_empty)

    # If no current measurement, nothing to compute
    if spool.weight_current is None:
        return None, total, None

    try:
        current = float(spool.weight_current)
    except Exception:
        return None, total, None

    # Bambu devices report filament-only (net)
    if is_bambu:
        remaining = max(0.0, current)
        percent = compute_remaining_percent(remaining, total)
        return remaining, total, percent

    # Non-Bambu: current may be either net (filament-only) or gross (spool+filament)
    empty = spool.weight_empty
    try:
        empty_val = float(empty) if empty is not None else None
    except Exception:
        empty_val = None

    remaining = None
    # If we know the total, prefer a candidate that falls into [0, total]
    if total is not None:
        # Candidate A: treat current as net filament
        candidate_net = current
        # Candidate B: treat current as gross -> subtract empty (if available)
        candidate_gross_net = (current - empty_val) if empty_val is not None else None

        if 0.0 <= candidate_net <= total:
            remaining = candidate_net
        elif candidate_gross_net is not None and 0.0 <= candidate_gross_net <= total:
            remaining = candidate_gross_net
        else:
            # Neither candidate fits perfectly; prefer candidate that is within a
            # reasonable bound: if candidate_gross_net is positive, use it;
            # otherwise fallback to candidate_net clamped to [0, total].
            if candidate_gross_net is not None and candidate_gross_net > 0:
                remaining = candidate_gross_net
            else:
                # Clamp candidate_net to [0, total]
                remaining = max(0.0, min(candidate_net, total))
    else:
        # Without total we can't validate; if empty provided, assume current is net
        # if it's plausibly small, otherwise subtract empty as fallback.
        if empty_val is None:
            remaining = current
        else:
            # If current - empty yields a positive value, assume gross; but
            # if current is small (< 1000) prefer treating as net.
            if current - empty_val > 0 and current > 1000:
                remaining = current - empty_val
            else:
                remaining = current

    remaining = max(0.0, remaining) if remaining is not None else None
    percent = compute_remaining_percent(remaining, total)
    return remaining, total, percent


def compute_fill_state(remaining_weight_g: Optional[float]) -> str:
    if remaining_weight_g is None:
        return "unknown"
    try:
        remaining = float(remaining_weight_g)
    except Exception:
        return "unknown"
    if remaining <= 0:
        return "empty"
    if remaining < 100:
        return "fast_empty"
    if remaining < 200:
        return "low"
    if remaining >= 700:
        return "full"
    return "ok"
