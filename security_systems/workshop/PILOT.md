# Pilot protocol — one session, three people, one line for the proposal

Workshop slots are scarce, and committees prefer a workshop that has been run with people over one that has only been run by a machine. A single small pilot is enough to write a true sentence about it. This page tells you how to run one and what you may claim afterwards.

## Who and when

- Two to four engineers who haven't seen the code. Colleagues, a meetup or friends all work; they need Python, not security experience.
- 90 minutes, run exactly as `INSTRUCTOR.md` says, with the same checkpoints and no extra help beyond what you'd give in the room.
- Send the setup block from `README.md` a day ahead, and ask each person to reply with the last line of `python -m workshop.check --implementation solution`.

## What to record

Copy this table and fill one row per participant. Record times from the start of the session.

| Participant | Setup worked before arrival? | Checkpoint 1 at (min) | Checkpoint 2 at (min) | Reached 7/7 at (min) | Used a recovery checkpoint? | Found an unmediated path in their own system? | Where they got stuck |
|---|---|---|---|---|---|---|---|
| P1 | | | | | | | |
| P2 | | | | | | | |
| P3 | | | | | | | |

At the end, ask the group two questions and write down the answers verbatim: *"What would you change?"* and *"What will you check in your own agents next week?"* Don't collect names, employers or proprietary code.

## What to change afterwards

- If most people reach checkpoint 1 after minute 30, cut the opening to five minutes and hand out step 1 earlier.
- If anyone's setup failed, add their exact error and fix to `README.md` under setup.
- If nobody found an unmediated path in their own system, spend more of the last 15 minutes on the worksheet and less on discussion.

## What you may then add to the proposals

Add one factual sentence to the Workshop pitch and the AI Con tutorial committee note, filled in from your table, for example:

> Piloted with three engineers new to the code: all three reached 7/7, the median time to 7/7 was 52 minutes, and the setup problem one hit is now fixed in the handout.

Use the real numbers, including a person who didn't finish. A committee trusts a pilot that reports friction more than one that reports none. Until a pilot has happened, the proposals say the kit is machine-tested and nothing more.
