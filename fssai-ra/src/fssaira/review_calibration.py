"""Reviewer canaries: measure oversight quality in operation, and cut capacity when it slips.

The oversight controls bound how much one reviewer may approve and how fast. They
cannot see whether the reviewer is actually reading. A simulation can model
attention; only the running system can measure it.

``ReviewerCalibration`` plants canaries -- items with a known, visible defect --
among real review items at a declared rate, indistinguishable in shape. A reviewer
who approves a canary has missed a defect that was there to be seen. Per reviewer,
the catch rate is estimated with a Wilson lower bound, so a lucky or unlucky
handful of canaries decides nothing; once enough canaries have been seen and the
bound falls below the floor, the reviewer's declared capacity is cut: fewer
approvals per window, a longer deliberation floor and an earlier second reviewer.
Capacity can only fall here; restoring it is a named human decision.

A canary never executes, whatever the reviewer decides: ``executable`` refuses it.
The measurement costs reviewer time, which is reported, not hidden.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field, replace

from .oversight import ReviewLoadPolicy

LOW = "REVIEWER_CALIBRATION_LOW"


def wilson_lower(successes: int, total: int, z: float = 1.96) -> float:
    if total == 0:
        return 0.0
    p = successes / total
    centre = p + z * z / (2 * total)
    margin = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total))
    return max(0.0, (centre - margin) / (1 + z * z / total))


@dataclass
class ReviewerCalibration:
    policy: ReviewLoadPolicy
    #: Required lower bound on the canary catch rate. Consistent with the default
    #: ``min_canaries``: ten canaries all caught give a Wilson lower bound of
    #: about 0.72, so a perfect reviewer passes, while nine in ten (about 0.60)
    #: does not pass at that sample size.
    floor: float = 0.7
    #: Canaries a reviewer must have decided before being judged.
    min_canaries: int = 10
    #: Share of the queue that is canaries.
    canary_rate: float = 0.1
    seed: int = 0
    _canaries: set = field(default_factory=set)
    _decisions: dict = field(default_factory=dict)

    def plant(self, items: list[dict], make_canary) -> list[dict]:
        """Interleave canaries among ``items``. ``make_canary(i)`` builds one of the same shape."""
        rng = random.Random(self.seed)
        count = max(1, round(len(items) * self.canary_rate))
        queue = list(items)
        for index in range(count):
            canary = make_canary(index)
            self._canaries.add(canary["id"])
            queue.insert(rng.randint(0, len(queue)), canary)
        return queue

    def is_canary(self, item_id: str) -> bool:
        return item_id in self._canaries

    def record(self, reviewer: str, item_id: str, approved: bool) -> None:
        if item_id in self._canaries:
            caught, seen = self._decisions.get(reviewer, (0, 0))
            self._decisions[reviewer] = (caught + (not approved), seen + 1)

    def executable(self, item_id: str) -> bool:
        """A canary is never executed, whatever the reviewer decided."""
        return item_id not in self._canaries

    def assessment(self, reviewer: str) -> dict:
        caught, seen = self._decisions.get(reviewer, (0, 0))
        lower = round(wilson_lower(caught, seen), 3)
        judged = seen >= self.min_canaries
        return {"reviewer": reviewer, "canaries": seen, "caught": caught,
                "catch_rate": round(caught / seen, 3) if seen else None,
                "catch_rate_lower_bound": lower, "judged": judged,
                "below_floor": judged and lower < self.floor,
                "code": LOW if judged and lower < self.floor else None}

    def policy_for(self, reviewer: str) -> ReviewLoadPolicy:
        """The reviewer's capacity: the declared policy, or a reduced one after missed canaries."""
        if not self.assessment(reviewer)["below_floor"]:
            return self.policy
        second = self.policy.second_reviewer_after
        return replace(
            self.policy,
            max_approvals_per_window=max(1, self.policy.max_approvals_per_window // 2),
            min_deliberation_seconds=self.policy.min_deliberation_seconds * 1.5,
            second_reviewer_after=1 if second is None else max(1, second // 2),
        )

    def cost(self, reviewer: str) -> dict:
        """Reviewer time spent on canaries, at the declared deliberation floor."""
        _caught, seen = self._decisions.get(reviewer, (0, 0))
        return {"canaries_reviewed": seen,
                "seconds_at_floor": seen * self.policy.min_deliberation_seconds}


__all__ = ["LOW", "ReviewerCalibration", "wilson_lower"]
