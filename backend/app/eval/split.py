"""Reproducible device/technique grouped split; no model or chain calls."""

import math
import random

EXCLUDED_TECHNIQUES = {"duplicate", "over_budget"}
SPLIT_NOTE = (
    "60/40 group shuffle, seed 42; public attacks grouped by device, seeds by technique. "
    "Devices approximate people; one person can use several devices. Public techniques "
    "may overlap across devices. Duplicate/over-budget attacks and their two rules are excluded."
)


def split_attacks(records):
    eligible, excluded = [], {"state_dependent": 0, "missing_group": 0}
    for record in sorted(records, key=lambda row: row["id"]):
        if record.get("technique") in EXCLUDED_TECHNIQUES:
            excluded["state_dependent"] += 1
            continue
        group = record.get("device_id") if record["source"] == "bounty" else record.get("technique")
        if not group:
            excluded["missing_group"] += 1
            continue
        eligible.append(dict(record, group=record["source"] + ":" + group))
    groups = sorted({row["group"] for row in eligible})
    random.Random(42).shuffle(groups)
    n_test = math.ceil(len(groups) * 0.4)
    heldout = set(groups[:n_test])
    return (
        [row for row in eligible if row["group"] not in heldout],
        [row for row in eligible if row["group"] in heldout],
        excluded,
    )


def wilson(successes, total):
    """95% Wilson score interval, NIST handbook PRC 7.2.4.1."""
    if total <= 0 or not 0 <= successes <= total:
        raise ValueError("A nonempty valid sample is required")
    z = 1.959963984540054
    p, z2 = successes / total, z * z
    divisor = 1 + z2 / total
    middle = (p + z2 / (2 * total)) / divisor
    radius = z * math.sqrt(p * (1 - p) / total + z2 / (4 * total * total)) / divisor
    return max(0.0, middle - radius), min(1.0, middle + radius)


def may_promote(v1, v2):
    return v2["catch"] > v1["catch"] and v2["false_alarm"] <= v1["false_alarm"]
