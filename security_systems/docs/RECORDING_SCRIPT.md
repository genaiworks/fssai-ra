# Four-minute proposal recording

This is the video to link from every proposal. Program committees weigh it heavily for a speaker they haven't seen. It covers Proposal 1 and shows enough of the method for Proposal 2 and the AI Con session.

**Setup (10 minutes).** Terminal at 20 pt or larger, dark background, window about 100 columns wide. Put your camera in a corner if your recorder allows it: a face beats a voice-over. Install once with `python -m pip install -e .`, then run `bash scripts/record_demo.sh` and press Enter at each beat. Everything is offline and deterministic, so a retake shows identical output. Upload as an unlisted YouTube or Loom video.

Speak to one engineer, not a room. Pauses are fine; the beats give you natural ones. Rehearse once against a timer rather than trusting the word count.

---

**Before beat 1, on camera (≈20 s)**

"Last year a coding agent deleted a production database during a code freeze it had been told to respect. The industry's answer was 'require human approval.' I'm Rachna Srivastava, and this talk is about what happens next: when the approval exists, but isn't bound to the action that runs."

**Beat 1 — an agent pipeline with deploy rights (≈40 s)**

"This is a small agent system with a coordinator, workers, a deploy tool and a secrets store. Everything passes through one dispatcher. A hijacked worker tries to read the secret and trigger a deploy: out of scope, both times. The coordinator asks to deploy: approval required. A human approves exactly one build. The first attempt to use that approval fails with a payload mismatch, because the arguments were different from what the human saw. The approved call runs, and a retry returns the same receipt without deploying twice. At the end, the summary that contains a secret is refused for the general channel and allowed for the security team."

**Beat 2 — borrowed authority (≈30 s)**

"Ten hostile delegation chains against three dispatchers. Trust the presented scope: zero stopped. Check each hop against its parent, which is what a careful team builds: two. Re-derive authority from the root on every call: all ten, and the legitimate chain still works."

**Beat 3 — replay with a forged approval (≈30 s)**

"This is the bug that humbled me. The original 203 tests all passed while a cache in front of my verifier returned a real deploy receipt to a forged approval. The fix is ordering: verify signature, audience, payload and expiry first, then serve the cache. One deploy effect, no matter how many retries."

**Beat 4 — "denied" is not a test result (≈35 s)**

"How did 203 tests miss it? They asserted on what the guard said. Look at the second row: the tool wrote an unreviewed build and then raised 'denied.' The refusal is true. The harm is also true. This oracle diffs the system of record instead, and it's forty lines of standard-library Python you can copy."

**Beat 5 — prove the attacker can win (≈25 s)**

"A zero only means something if the attack could have worked. Three hundred fuzzed attacks: zero effects. Remove one control, the execution mediator: a hundred and five. Now the zero is evidence."

**Beat 6 — which controls can we delete? (≈30 s)**

"Mutation testing for guardrails. Remove residency alone: nothing breaks. Remove model attestation alone: nothing breaks. A naive study deletes both. Remove them together, and sensitive data reaches the weaker model again. The same happens with the two replay defenses below. They aren't dead code; each one is the other's backup."

**Close, on camera (≈20 s)**

"Everything you saw runs offline from a public repository, and every number regenerates from a clean checkout. Attendees leave with the dispatcher pattern, the oracle, and a worksheet for their own agents. The numbers come from synthetic worlds, and the method is what transfers. Thanks for watching."

---

Before uploading, check that the video shows 0 and 105 in beat 5 and that every figure you speak is on screen. If you retake only part of it, retake whole beats so the terminal output matches the words.
