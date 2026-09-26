"""Revocation under partitions, duplicates, delay and clock skew.

Epoch revocation is simple to state: withdraw consent, raise the epoch, and
every queued write, stale lease and later release fails. In one process with one
database that is a transaction. Across a gateway, a consent store and several
external adapters it is a distributed-systems claim, and those fail in the gaps
between messages: a check that raced a revocation, a lease judged fresh by a
skewed clock, a retry that sent the email twice.

This harness makes the claim falsifiable. It is a deterministic, seeded
discrete-event simulation of one authority store and several adapters joined by
a network that drops, duplicates, delays and partitions messages, with adapter
clocks skewed against the store's. The same workload and the same faults run
under four commit disciplines:

``fenced`` (the design)
    The adapter asks the store to *commit* ``(effect, epoch)``; the store checks
    the epoch and records the commit in one linearizable step, idempotently. The
    commit is the point of no return. The adapter applies only an effect the
    store committed, at most once per effect id. A partitioned adapter that
    cannot reach the store holds the effect; it never decides alone.

``check_then_act`` (ablation)
    The adapter reads the epoch, then applies after its own processing time.
    Revocation between the read and the act goes through.

``local_clock_lease`` (ablation)
    The adapter caches a freshness proof and judges its age by its own clock.
    A slow clock or a partition extends authority past revocation.

``no_idempotency`` (ablation)
    Fenced commits, but the adapter does not deduplicate: a duplicated reply
    applies the effect twice.

Invariants, checked on every run:

* **no stale effect** -- no effect's point of no return (the store commit for a
  fenced discipline, the application itself otherwise) lies after the
  revocation of the epoch it was authorised under;
* **exactly once** -- no effect is applied twice;
* **reconciled** -- after the reconciler replays committed-but-undelivered
  effects, the committed set equals the applied set (fenced disciplines).

The simulation models the protocol, not a particular database or broker; a
deployment qualifies its own store and adapters with the same invariants.
"""
from __future__ import annotations

import heapq
import random
from dataclasses import asdict, dataclass, field

DISCIPLINES = ("fenced", "check_then_act", "local_clock_lease", "no_idempotency")


@dataclass(frozen=True)
class ChaosConfig:
    tasks: int = 6
    effects_per_task: int = 12
    adapters: int = 3
    horizon: float = 60.0
    revoked_fraction: float = 0.75
    min_delay: float = 0.05
    max_delay: float = 2.0
    duplicate_rate: float = 0.15
    loss_rate: float = 0.05
    partitions_per_adapter: int = 2
    min_partition: float = 2.0
    max_partition: float = 8.0
    max_skew: float = 5.0
    lease_seconds: float = 3.0
    max_processing: float = 1.5
    retry_every: float = 1.0


@dataclass
class _Effect:
    id: str
    task: int
    epoch: int
    adapter: int
    applied: list[float] = field(default_factory=list)
    linearized_at: float | None = None
    refused: bool = False


class _Sim:
    def __init__(self, config: ChaosConfig, discipline: str, seed: int) -> None:
        if discipline not in DISCIPLINES:
            raise ValueError(f"unknown discipline {discipline!r}")
        self.c, self.discipline = config, discipline
        self.rng = random.Random(seed)
        self.queue: list = []
        self.seq = 0
        self.now = 0.0
        self.epoch = [0] * config.tasks
        self.revoked_at: list[float | None] = [None] * config.tasks
        self.committed: dict[str, float] = {}
        self.effects: dict[str, _Effect] = {}
        self.leases: dict[tuple[int, int], tuple[int, float]] = {}
        rng = self.rng
        self.skew = [rng.uniform(-config.max_skew, config.max_skew) for _ in range(config.adapters)]
        self.partitions = [
            [(s, s + rng.uniform(config.min_partition, config.max_partition))
             for s in (rng.uniform(0, config.horizon) for _ in range(config.partitions_per_adapter))]
            for _ in range(config.adapters)]

    # -- plumbing -----------------------------------------------------------
    def at(self, when: float, kind: str, **data) -> None:
        self.seq += 1
        heapq.heappush(self.queue, (when, self.seq, kind, data))

    def partitioned(self, adapter: int) -> bool:
        return any(s <= self.now < e for s, e in self.partitions[adapter])

    def send(self, kind: str, adapter: int, **data) -> None:
        """A message on the adapter<->store link: lost, delayed, duplicated, cut."""
        if self.partitioned(adapter) or self.rng.random() < self.c.loss_rate:
            return
        self.at(self.now + self.rng.uniform(self.c.min_delay, self.c.max_delay), kind, **data)
        if self.rng.random() < self.c.duplicate_rate:
            self.at(self.now + self.rng.uniform(self.c.min_delay, self.c.max_delay), kind, **data)

    # -- workload -----------------------------------------------------------
    def setup(self) -> None:
        c, rng = self.c, self.rng
        for task in range(c.tasks):
            for n in range(c.effects_per_task):
                effect = _Effect(f"t{task}-e{n}", task, 0, rng.randrange(c.adapters))
                self.effects[effect.id] = effect
                self.at(rng.uniform(0, c.horizon), "request", effect=effect.id)
            if rng.random() < c.revoked_fraction:
                self.at(rng.uniform(0, c.horizon), "revoke", task=task)

    def run(self) -> None:
        self.setup()
        deadline = self.c.horizon * 4
        while self.queue:
            when, _, kind, data = heapq.heappop(self.queue)
            if when > deadline:
                break
            self.now = when
            getattr(self, "on_" + kind)(**data)

    # -- the authority store (linearizable: one event at a time) -------------
    def on_revoke(self, task: int) -> None:
        self.epoch[task] += 1
        if self.revoked_at[task] is None:
            self.revoked_at[task] = self.now

    def on_commit_request(self, effect: str) -> None:
        e = self.effects[effect]
        if effect in self.committed:                       # idempotent replay
            self.send("commit_reply", e.adapter, effect=effect, ok=True)
        elif self.epoch[e.task] == e.epoch:
            self.committed[effect] = self.now
            self.send("commit_reply", e.adapter, effect=effect, ok=True)
        else:
            self.send("commit_reply", e.adapter, effect=effect, ok=False)

    def on_epoch_read(self, effect: str) -> None:
        e = self.effects[effect]
        self.send("epoch_reply", e.adapter, effect=effect, epoch=self.epoch[e.task],
                  issued=self.now)

    # -- adapters -----------------------------------------------------------
    def resolved(self, e: _Effect) -> bool:
        return bool(e.applied) or e.refused

    def apply(self, e: _Effect, linearized_at: float) -> None:
        if e.applied and self.discipline != "no_idempotency":
            return                                        # idempotency key
        e.applied.append(self.now)
        if e.linearized_at is None:
            e.linearized_at = linearized_at

    def on_request(self, effect: str) -> None:
        e = self.effects[effect]
        if self.resolved(e):
            return
        if self.discipline in ("fenced", "no_idempotency"):
            self.send("commit_request", e.adapter, effect=effect)
            self.at(self.now + self.c.retry_every, "request", effect=effect)
        elif self.discipline == "check_then_act":
            self.send("epoch_read", e.adapter, effect=effect)
            self.at(self.now + self.c.retry_every, "request", effect=effect)
        else:                                             # local_clock_lease
            lease = self.leases.get((e.adapter, e.task))
            local_now = self.now + self.skew[e.adapter]
            if lease and lease[0] == e.epoch and local_now - lease[1] <= self.c.lease_seconds:
                self.apply(e, self.now)
            else:
                self.send("epoch_read", e.adapter, effect=effect)
                self.at(self.now + self.c.retry_every, "request", effect=effect)

    def on_commit_reply(self, effect: str, ok: bool) -> None:
        e = self.effects[effect]
        if not ok:
            e.refused = not e.applied
            return
        self.apply(e, self.committed[effect])

    def on_epoch_reply(self, effect: str, epoch: int, issued: float) -> None:
        e = self.effects[effect]
        if self.discipline == "local_clock_lease":
            # The proof carries the store's issue time; the adapter judges its
            # age against its own clock, which is where skew bites.
            self.leases[(e.adapter, e.task)] = (epoch, issued)
            if epoch == e.epoch and not self.resolved(e):
                self.apply(e, self.now)
            elif epoch != e.epoch:
                e.refused = not e.applied
            return
        if epoch != e.epoch:
            e.refused = not e.applied
            return
        self.at(self.now + self.rng.uniform(0, self.c.max_processing), "act", effect=effect)

    def on_act(self, effect: str) -> None:
        e = self.effects[effect]
        if not e.applied:
            self.apply(e, self.now)

    # -- after the run ------------------------------------------------------
    def reconcile(self) -> int:
        """Deliver committed effects whose reply never arrived, once."""
        replayed = 0
        if self.discipline in ("fenced", "no_idempotency"):
            for effect, committed_at in self.committed.items():
                e = self.effects[effect]
                if not e.applied:
                    e.applied.append(self.now)
                    e.linearized_at = committed_at
                    replayed += 1
        return replayed

    def report(self) -> dict:
        replayed = self.reconcile()
        stale = duplicate = in_flight = 0
        max_lag = 0.0
        for e in self.effects.values():
            revoked = self.revoked_at[e.task]
            if len(e.applied) > 1:
                duplicate += 1
            if not e.applied or revoked is None:
                continue
            if e.linearized_at is not None and e.linearized_at > revoked:
                stale += 1
            elif max(e.applied) > revoked:
                in_flight += 1
                max_lag = max(max_lag, max(e.applied) - revoked)
        fenced = self.discipline in ("fenced", "no_idempotency")
        applied = {k for k, e in self.effects.items() if e.applied}
        return {
            "discipline": self.discipline,
            "effects": len(self.effects),
            "applied": len(applied),
            "refused_stale": sum(e.refused and not e.applied for e in self.effects.values()),
            "held": sum(not e.applied and not e.refused for e in self.effects.values()),
            "stale_effects": stale,
            "duplicate_applications": duplicate,
            "unreconciled": len(applied ^ set(self.committed)) if fenced else None,
            "reconciled_by_replay": replayed,
            "committed_before_revoke_delivered_after": in_flight,
            "max_delivery_lag_after_revoke": round(max_lag, 3),
        }


def run_once(discipline: str, seed: int, config: ChaosConfig | None = None) -> dict:
    sim = _Sim(config or ChaosConfig(), discipline, seed)
    sim.run()
    return sim.report()


def run_campaign(*, seeds: int = 200, config: ChaosConfig | None = None,
                 disciplines: tuple[str, ...] = DISCIPLINES) -> dict:
    """Every discipline against the same seeded faults; the design must be clean."""
    config = config or ChaosConfig()
    arms = {}
    for discipline in disciplines:
        runs = [run_once(discipline, seed, config) for seed in range(seeds)]
        arms[discipline] = {
            "runs": seeds,
            "runs_with_stale_effect": sum(r["stale_effects"] > 0 for r in runs),
            "stale_effects": sum(r["stale_effects"] for r in runs),
            "duplicate_applications": sum(r["duplicate_applications"] for r in runs),
            "unreconciled": (sum(r["unreconciled"] for r in runs)
                             if runs[0]["unreconciled"] is not None else None),
            "applied": sum(r["applied"] for r in runs),
            "refused_stale": sum(r["refused_stale"] for r in runs),
            "held_by_partition": sum(r["held"] for r in runs),
            "max_delivery_lag_after_revoke": max(r["max_delivery_lag_after_revoke"] for r in runs),
        }
    design = arms.get("fenced")
    return {
        "config": asdict(config),
        "arms": arms,
        "design_holds": design is not None and design["stale_effects"] == 0
        and design["duplicate_applications"] == 0 and design["unreconciled"] == 0,
        "ablations_detected": {d: a["stale_effects"] + a["duplicate_applications"] > 0
                               for d, a in arms.items() if d != "fenced"},
        "reading": ("fenced commit is the only discipline with zero stale and zero duplicate "
                    "effects; each ablation removes one property and its violation appears"),
    }


__all__ = ["ChaosConfig", "DISCIPLINES", "run_campaign", "run_once"]
