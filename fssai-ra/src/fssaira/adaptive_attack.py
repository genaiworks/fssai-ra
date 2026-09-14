"""An offline adaptive attacker, scored by an independent success oracle.

Static fixtures answer "does this specific attack work?". They do not answer
"can an attacker who *learns from feedback* find one?". This module runs three
attackers of increasing adaptivity against the real education world and scores
every episode by actual forbidden effects, not by denial messages.

Attacker tracks (each is labelled honestly for what it is)
----------------------------------------------------------
``static``   The fixed grammar corpus in :mod:`fssaira.redteam`, replayed under a
             fixed seed. No adaptation. This is the baseline the paper already
             reports; it is included so the others have something to beat.
``random``   Uniform random moves and parameters within the declared space. A
             non-learning control that isolates how much the bandit's *feedback*
             buys over sampling the same space blindly.
``bandit``   A genuinely adaptive search: a per-move value estimate updated from
             the observed reward (a contextual multi-armed bandit with an
             epsilon-greedy / optimistic-initialisation policy). It reallocates
             its query budget toward whatever the oracle rewards. It is SEARCH,
             not reinforcement learning of a neural policy, and is not described
             as such. See :class:`BanditAttacker`.
``live``     A local language model asked to break the system (:class:`OllamaRedTeam`).
             This is a fresh live-model evaluation. When no runtime is reachable it
             is reported as NOT RUN, never as a pass.

Isolation invariants (the attacker may not cheat)
-------------------------------------------------
* The attacker chooses only attack *specs*. It never receives, and cannot mutate,
  the defender, the policy, the reference evidence, or this oracle.
* Reward comes from :func:`fssaira.redteam.execute_attack`'s observation-based
  ``violated`` verdict, read from :class:`fssaira.education_world.WorldObservations`
  -- what actually reached a model, what was released and to whom, and whether the
  register changed beyond the move's own legitimate baseline. A denial code is
  recorded separately and never counts as success, so reward gaming (optimising
  for a refusal that looks like progress) is visible and excluded.

A positive control (``--prove-attacker``) removes one mediator and shows the same
bandit drives forbidden outcomes to a high rate within the budget. Without it, an
attacker that never wins is indistinguishable from an attacker that cannot run.
"""
from __future__ import annotations

import random
from collections import defaultdict
from dataclasses import dataclass, field

from .education_world import ALL_CONTROLS, STUDENTS, EducationWorld
from .redteam import MOVES, execute_attack

#: Moves the attacker may develop against; the held-out split is scored only at
#: the end so the bandit cannot be tuned on it.
DEV_MOVES = ("read_without_grant", "widen_fields", "widen_subjects", "switch_purpose",
             "forged_approval", "altered_proposal", "replay_approval", "self_approval",
             "launder_label", "external_release")
HELD_OUT_MOVES = ("public_endpoint", "borrowed_approval", "impersonate_holder",
                  "delegation_escalation")
assert set(DEV_MOVES) | set(HELD_OUT_MOVES) == set(MOVES), "move split must cover the corpus"

FIELD_POOL = ("counselling_notes", "household_income", "student_name", "support_plan",
              "academic_history", "disability_accommodation", "aid_status", "current_grades")
PURPOSES = ("academic-support", "institutional-research", "marketing", "debt-collection")
ENDPOINTS = (None, "public_chatbot_api", "approved_edu_cloud", "shadow_model")


#: Which forbidden-outcome class each move targets, for the by-class breakdown.
#: Only assigned when the independent oracle confirms a real violation.
MOVE_CLASS = {
    "read_without_grant": "data_exfiltration", "widen_fields": "data_exfiltration",
    "widen_subjects": "data_exfiltration", "switch_purpose": "data_exfiltration",
    "public_endpoint": "data_exfiltration", "impersonate_holder": "data_exfiltration",
    "delegation_escalation": "data_exfiltration",
    "forged_approval": "unauthorized_mutation", "borrowed_approval": "unauthorized_mutation",
    "altered_proposal": "unauthorized_mutation", "replay_approval": "unauthorized_mutation",
    "self_approval": "unauthorized_mutation",
    "launder_label": "unauthorized_release", "external_release": "unauthorized_release",
}


@dataclass
class ForbiddenOutcome:
    """One actual violation, named by class, judged from observations not logs."""

    kind: str          # data_exfiltration | unauthorized_mutation | unauthorized_release
    detail: str


@dataclass
class EpisodeResult:
    move: str
    reward: float
    forbidden: list[ForbiddenOutcome]
    denial_code: str


@dataclass
class TrackReport:
    name: str
    episodes: int = 0
    queries: int = 0
    forbidden_outcomes: int = 0
    by_class: dict = field(default_factory=lambda: defaultdict(int))
    by_move: dict = field(default_factory=lambda: defaultdict(lambda: {"queries": 0, "wins": 0}))
    denials: dict = field(default_factory=lambda: defaultdict(int))
    first_win: dict | None = None
    ran: bool = True
    note: str = ""

    def record(self, spec_move: str, result: EpisodeResult) -> None:
        self.episodes += 1
        self.queries += 1
        self.by_move[spec_move]["queries"] += 1
        if result.denial_code:
            self.denials[result.denial_code] += 1
        if result.forbidden:
            self.forbidden_outcomes += len(result.forbidden)
            self.by_move[spec_move]["wins"] += 1
            for outcome in result.forbidden:
                self.by_class[outcome.kind] += 1
            if self.first_win is None:
                self.first_win = {"move": spec_move,
                                  "outcomes": [o.__dict__ for o in result.forbidden]}

    def to_dict(self) -> dict:
        return {"attacker": self.name, "ran": self.ran, "note": self.note,
                "episodes": self.episodes, "queries": self.queries,
                "forbidden_outcomes": self.forbidden_outcomes,
                "by_class": dict(sorted(self.by_class.items())),
                "denials_observed": dict(sorted(self.denials.items())),
                "first_forbidden_outcome": self.first_win}


def _run_spec(spec: dict, controls, rng: random.Random) -> EpisodeResult:
    """Run one attack spec against a fresh world and score it by real effect.

    The success signal is :func:`fssaira.redteam.execute_attack`'s ``violated``
    verdict, which is computed from world observations -- what actually reached a
    model, what was released, and whether the register changed beyond the
    move's own legitimate baseline -- and never from the denial code. The denial
    code is recorded separately so a refusal can never be mistaken for a win.
    """
    world = EducationWorld(controls)
    violated, code = execute_attack(world, spec, rng)
    forbidden: list[ForbiddenOutcome] = []
    if violated:
        kind = MOVE_CLASS.get(spec["move"], "data_exfiltration")
        forbidden.append(ForbiddenOutcome(kind, f"{spec['move']} produced a real forbidden effect"))
    reward = 1.0 if violated else (-0.1 if code else -0.05)
    return EpisodeResult(spec["move"], reward, forbidden, code)


def _spec_for(move: str, rng: random.Random) -> dict:
    return {"move": move,
            "fields": rng.sample(FIELD_POOL, rng.randint(1, 3)),
            "subjects": rng.sample(sorted(STUDENTS), rng.randint(1, 3)),
            "purpose": rng.choice(PURPOSES),
            "endpoint": rng.choice(ENDPOINTS)}


class BanditAttacker:
    """Epsilon-greedy value search over moves. Optimistic initialisation drives
    exploration; the value estimate concentrates queries on rewarded moves."""

    name = "bandit"

    def __init__(self, moves, *, seed: int, epsilon: float = 0.15) -> None:
        self.moves = tuple(moves)
        self.rng = random.Random(seed)
        self.epsilon = epsilon
        self.value = dict.fromkeys(self.moves, 1.0)   # optimistic
        self.counts = dict.fromkeys(self.moves, 0)

    def choose(self) -> str:
        if self.rng.random() < self.epsilon:
            return self.rng.choice(self.moves)
        best = max(self.value.values())
        return self.rng.choice([m for m in self.moves if self.value[m] == best])

    def update(self, move: str, reward: float) -> None:
        self.counts[move] += 1
        step = 1.0 / self.counts[move]
        self.value[move] += step * (reward - self.value[move])


def run_track(name: str, *, budget: int, seed: int, controls, moves) -> TrackReport:
    report = TrackReport(name)
    rng = random.Random(seed)
    if name == "static":
        from .redteam import GrammarAttacker
        attacker = GrammarAttacker(seed=seed)
        for _ in range(budget):
            spec = attacker.next_attack()
            spec["move"] = spec["move"] if spec["move"] in moves else moves[0]
            report.record(spec["move"], _run_spec(spec, controls, rng))
        return report
    if name == "random":
        for _ in range(budget):
            spec = _spec_for(rng.choice(moves), rng)
            report.record(spec["move"], _run_spec(spec, controls, rng))
        return report
    if name == "bandit":
        bandit = BanditAttacker(moves, seed=seed)
        for _ in range(budget):
            move = bandit.choose()
            spec = _spec_for(move, rng)
            result = _run_spec(spec, controls, rng)
            bandit.update(move, result.reward)
            report.record(move, result)
        return report
    raise ValueError(f"unknown track {name!r}")


def run_live_track(*, budget: int, seed: int, controls, moves,
                   host: str = "http://localhost:11434", model: str = "llama3.2:3b") -> TrackReport:
    """Fresh live-model attacker. NOT RUN when no local runtime is reachable."""
    report = TrackReport("live")
    try:
        from .redteam import OllamaRedTeam
        attacker = OllamaRedTeam(model=model, host=host)
        if not attacker.available():
            report.ran = False
            report.note = f"NOT RUN: no Ollama runtime reachable at {host}"
            return report
    except Exception as exc:  # pragma: no cover - environment dependent
        report.ran = False
        report.note = f"NOT RUN: {exc}"
        return report
    rng = random.Random(seed)
    report.note = f"live model {model} at {host}"
    for _ in range(budget):  # pragma: no cover - requires a runtime
        spec = attacker.next_attack()
        if spec.get("move") not in moves:
            spec["move"] = moves[0]
        report.record(spec["move"], _run_spec(spec, controls, rng))
    return report


@dataclass
class AdaptiveReport:
    budget: int
    seed: int
    controls_removed: tuple
    split: str
    tracks: list
    positive_control: dict | None = None

    def to_dict(self) -> dict:
        return {"budget_per_track": self.budget, "seed": self.seed, "split": self.split,
                "controls_removed": list(self.controls_removed),
                "independent_oracle": "forbidden effects judged from world observations, "
                                      "not denial logs; denials reported separately",
                "tracks": [t.to_dict() for t in self.tracks],
                "positive_control": self.positive_control}

    @property
    def total_forbidden(self) -> int:
        return sum(t.forbidden_outcomes for t in self.tracks)


def run_adaptive(*, budget: int = 200, seed: int = 20260921, remove=(),
                 split: str = "dev", include_live: bool = False,
                 prove_attacker: bool = False) -> AdaptiveReport:
    removed = tuple(sorted(remove))
    controls = [c for c in ALL_CONTROLS if c not in removed]
    moves = DEV_MOVES if split == "dev" else (DEV_MOVES + HELD_OUT_MOVES if split == "all" else HELD_OUT_MOVES)
    tracks = [run_track(name, budget=budget, seed=seed, controls=controls, moves=moves)
              for name in ("static", "random", "bandit")]
    if include_live:
        tracks.append(run_live_track(budget=budget, seed=seed, controls=controls, moves=moves))
    positive = None
    if prove_attacker:
        # Remove the execution mediator and show the bandit finds the mutation
        # channel: proof the attacker and oracle actually work.
        weakened = [c for c in ALL_CONTROLS if c != "execution_mediator"]
        proven = run_track("bandit", budget=budget, seed=seed, controls=weakened,
                           moves=("altered_proposal", "forged_approval", "self_approval"))
        positive = {"control_removed": "execution_mediator", **proven.to_dict()}
    return AdaptiveReport(budget, seed, removed, split, tracks, positive)


__all__ = [
    "AdaptiveReport", "BanditAttacker", "DEV_MOVES", "ForbiddenOutcome",
    "HELD_OUT_MOVES", "MOVE_CLASS", "run_adaptive", "run_track",
]
