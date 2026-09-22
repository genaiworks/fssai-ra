"""Human review as a bounded resource: overload never becomes approval.

An oversight monitor bounds what one reviewer may approve. This module governs
the queue in front of the reviewers, which is where review silently fails in
practice: the backlog grows, a timeout fires, and some well-meaning default turns
"nobody looked" into "approved". The invariant here is the one the architecture
needs and the one most workflow engines do not state:

    **An item is approved only by a named human reviewer's decision. Queue depth,
    reviewer capacity, and timeouts can defer, escalate, or refuse an item. They
    can never approve it.**

The unsafe policy ``auto_approve_on_overload`` exists only so the ablation can show
what that common default does. Domain packs cannot select it (:mod:`trustkernel.kernel.pack_floor`
rejects it) and :meth:`BoundedReviewQueue.for_pack` never constructs it.
"""
from __future__ import annotations

from dataclasses import dataclass, field

SAFE_POLICIES = ("defer_to_manual", "escalate", "queue")
UNSAFE_ABLATION_POLICY = "auto_approve_on_overload"


class ReviewState:
    QUEUED = "QUEUED"
    ESCALATED = "ESCALATED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    DEFERRED_TO_MANUAL = "DEFERRED_TO_MANUAL"
    TIMED_OUT = "TIMED_OUT"


class ReviewCode:
    REVIEWER_UNKNOWN = "REVIEWER_NOT_A_DECLARED_HUMAN"
    REVIEWER_OVER_CAPACITY = "REVIEWER_OVER_CAPACITY"
    ITEM_NOT_PENDING = "REVIEW_ITEM_NOT_PENDING"
    SELF_REVIEW = "REVIEWER_IS_REQUESTER"
    WRONG_ROLE = "REVIEWER_ROLE_NOT_PERMITTED"


class ReviewRefused(PermissionError):
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code


@dataclass
class ReviewItem:
    item_id: str
    proposal_digest: str
    requester: str
    required_role: str
    submitted_at: float
    state: str
    decided_by: str = ""
    decided_at: float = 0.0
    history: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"item_id": self.item_id, "proposal_digest": self.proposal_digest,
                "requester": self.requester, "required_role": self.required_role,
                "state": self.state, "decided_by": self.decided_by, "history": list(self.history)}


class BoundedReviewQueue:
    def __init__(self, *, capacity_per_window: int, window_seconds: int, queue_limit: int,
                 timeout_seconds: int, escalation_role: str, reviewers: dict[str, str],
                 overload_policy: str = "defer_to_manual") -> None:
        if overload_policy not in (*SAFE_POLICIES, UNSAFE_ABLATION_POLICY):
            raise ValueError(f"unknown overload policy {overload_policy!r}")
        if min(capacity_per_window, window_seconds, queue_limit, timeout_seconds) <= 0:
            raise ValueError("review capacity, window, queue limit, and timeout must be positive")
        self.capacity = capacity_per_window
        self.window = window_seconds
        self.queue_limit = queue_limit
        self.timeout = timeout_seconds
        self.escalation_role = escalation_role
        self.reviewers = dict(reviewers)
        self.policy = overload_policy
        self.items: dict[str, ReviewItem] = {}
        self._decisions: list[tuple[str, float]] = []

    @classmethod
    def for_pack(cls, review: dict, reviewers: dict[str, str]) -> BoundedReviewQueue:
        policy = review.get("overload_policy")
        if policy not in SAFE_POLICIES:
            raise ValueError(f"a pack may not select overload policy {policy!r}")
        return cls(capacity_per_window=review["capacity_per_window"],
                   window_seconds=review["window_seconds"], queue_limit=review["queue_limit"],
                   timeout_seconds=review["timeout_seconds"],
                   escalation_role=review["escalation_role"], reviewers=reviewers,
                   overload_policy=policy)

    # -- queue ---------------------------------------------------------------
    def depth(self) -> int:
        return sum(1 for item in self.items.values()
                   if item.state in (ReviewState.QUEUED, ReviewState.ESCALATED))

    def submit(self, *, item_id: str, proposal_digest: str, requester: str, required_role: str,
               now: float) -> ReviewItem:
        self.expire(now)
        item = ReviewItem(item_id, proposal_digest, requester, required_role, now, ReviewState.QUEUED)
        if self.depth() >= self.queue_limit:
            if self.policy == "defer_to_manual":
                item.state = ReviewState.DEFERRED_TO_MANUAL
            elif self.policy == "escalate":
                item.state = ReviewState.ESCALATED
                item.required_role = self.escalation_role
            elif self.policy == "queue":
                item.state = ReviewState.DEFERRED_TO_MANUAL
            else:  # UNSAFE_ABLATION_POLICY: the default this module exists to forbid
                item.state = ReviewState.APPROVED
                item.decided_by = ""
        item.history.append((now, item.state, "overload" if self.depth() >= self.queue_limit else "admitted"))
        self.items[item_id] = item
        return item

    def expire(self, now: float) -> int:
        """Pending items past their timeout go to the manual fallback. None is approved."""
        expired = 0
        for item in self.items.values():
            if item.state in (ReviewState.QUEUED, ReviewState.ESCALATED) and \
                    now - item.submitted_at >= self.timeout:
                item.state = ReviewState.TIMED_OUT
                item.history.append((now, item.state, "timeout: routed to manual fallback"))
                expired += 1
        return expired

    def _used(self, reviewer: str, now: float) -> int:
        return sum(1 for who, at in self._decisions if who == reviewer and now - at < self.window)

    def decide(self, item_id: str, *, reviewer: str, approve: bool, now: float) -> ReviewItem:
        self.expire(now)
        item = self.items.get(item_id)
        if item is None or item.state not in (ReviewState.QUEUED, ReviewState.ESCALATED):
            raise ReviewRefused(ReviewCode.ITEM_NOT_PENDING, f"{item_id} is not awaiting review")
        role = self.reviewers.get(reviewer)
        if role is None:
            raise ReviewRefused(ReviewCode.REVIEWER_UNKNOWN, f"{reviewer} is not a declared reviewer")
        if reviewer == item.requester:
            raise ReviewRefused(ReviewCode.SELF_REVIEW, "a requester cannot review their own item")
        if role != item.required_role:
            raise ReviewRefused(ReviewCode.WRONG_ROLE, f"{item_id} needs {item.required_role}")
        if self._used(reviewer, now) >= self.capacity:
            if self.policy == "escalate" and item.state != ReviewState.ESCALATED:
                item.state = ReviewState.ESCALATED
                item.required_role = self.escalation_role
                item.history.append((now, item.state, f"{reviewer} over capacity: escalated"))
            raise ReviewRefused(ReviewCode.REVIEWER_OVER_CAPACITY,
                                f"{reviewer} has used their declared capacity for this window")
        item.state = ReviewState.APPROVED if approve else ReviewState.REJECTED
        item.decided_by = reviewer
        item.decided_at = now
        item.history.append((now, item.state, f"decided by {reviewer} ({role})"))
        self._decisions.append((reviewer, now))
        return item

    # -- invariants ------------------------------------------------------------
    def approved_without_human(self) -> list[ReviewItem]:
        return [item for item in self.items.values()
                if item.state == ReviewState.APPROVED and item.decided_by not in self.reviewers]

    def stats(self) -> dict:
        counts: dict[str, int] = {}
        for item in self.items.values():
            counts[item.state] = counts.get(item.state, 0) + 1
        return {"policy": self.policy, "submitted": len(self.items), "by_state": dict(sorted(counts.items())),
                "approved_without_human": len(self.approved_without_human()),
                "queue_limit": self.queue_limit, "capacity_per_window": self.capacity}


__all__ = ["BoundedReviewQueue", "ReviewCode", "ReviewItem", "ReviewRefused", "ReviewState",
           "SAFE_POLICIES", "UNSAFE_ABLATION_POLICY"]
