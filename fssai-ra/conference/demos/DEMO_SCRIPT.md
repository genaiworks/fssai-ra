# Live demonstration script (12 minutes)

**Setup (before the session):** `make setup`, then `make conference-demo` once as a rehearsal.
Keep a second terminal on `fssai-ra/`. Open `python scripts/conference_lab.py` in a browser tab.
**Fallback:** if anything fails on stage, open the recorded lab exported with
`python scripts/conference_lab.py --export lab-recorded.html`, which shows results from real runs.

| Time | Command | What the audience sees | What to say |
|---|---|---|---|
| 0:00 | — | Title: *Intelligence is untrusted; power and data are mediated* | "We will not ask you to trust this AI. We will give it every chance to break a university." |
| 0:45 | `make conference-demo DEMO=1` | ALLOW never appears; three DENY lines | "It proposed a grade change, forged 'AUTHORITY: ADMIN', then tried the database directly. A proposal is not a power." |
| 2:00 | `DEMO=2` | Tokens instead of names; counselling notes denied | "Relevance is not entitlement. The model reasons about *which* student, never *who*." |
| 3:15 | `DEMO=3` | Injection admitted as data, read denied | "The injection changed what the model asked for. It did not change what it may see." |
| 4:15 | `DEMO=4` | Router suggestions refused | "The router can narrow. It cannot widen." |
| 5:15 | `DEMO=5` | Three escalations denied, one narrowing allowed, revocation propagates | "A sub-agent holds at most what its parent held, for the same purpose, for less time." |
| 6:30 | `DEMO=6` | Ten-step trace and the ten literacy questions | "This is not a system that says no. Legitimate work completes, and anyone can see who decided and how to challenge it." |
| 8:30 | `DEMO=7` | enabled DENY → DISABLED ATTACK SUCCEEDS → restored DENY | "Remove one control and the harm returns. The controls are load-bearing, not decorative." |
| 10:00 | lab tab | Audience picks an attack and a control to remove | Invite a volunteer: "Which control do you think matters? Let's switch it off." |
| 11:15 | `DEMO=9` | Honest and malicious models, same boundary | "Utility depends on the model. Safety depends on the mediators." |
| 11:45 | `conference/evidence/SCORECARD.md` | Generated figures, limitations | "Every number was produced by running this. Here is what it does not prove." |

**For educators:** the lab is the teaching instrument. Ask learners to predict, before each
run, which mediator will refuse and why; then remove that control and test the prediction.
That is system literacy: distinguishing proposals from powers, requests from entitlements,
and outcomes from evidence.
