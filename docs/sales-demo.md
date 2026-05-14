# Earnings Reaction Playbook — Sales Demo Walkthrough

**Purpose:** One-page script for live demos in booked Prudentia AI strategy sessions. Tells the buyer's story, not the engineer's.

**Audience:** A mid-sized firm's COO, head of trading, or CIO who has heard the AI pitch and wants to see something work.

**Total demo time:** 8 minutes. Anything longer and they tune out.

---

## Pre-demo (offline, before joining the call)

Run through [`docs/pre-demo-checklist.md`](pre-demo-checklist.md). Two minutes. Don't skip it.

---

## Opening (60 seconds)

> "Most AI demos show a chatbot. This isn't that. What you're about to see is a workflow — six investment analysts, each with a distinct lens, all run by a controller that doesn't need you to babysit it. The whole thing finishes in about three minutes for a single ticker. We're going to point it at a real company that just reported earnings.
>
> Two questions to keep in mind: would *your* team find this useful, and would you trust the output?"

Pull up the live system. **Do not show terminal output on screen.** Use the streaming UI.

---

## Live run (4 minutes)

1. **Pick a ticker.** Use one the prospect named in the discovery call, or default to a recently-reported ticker rehearsed in the pre-demo checklist. Type it. Hit run.
2. **Narrate the fan-out (10 seconds):** "Six analysts kick off in parallel — fundamentals, sentiment, technicals, valuation, plus two persona lenses we curated: Warren Buffett's long-term view and Michael Burry's contrarian view. They share state but reason independently."
3. **Let the stream run.** Don't fill the silence — let them watch nodes light up in the UI. This is the moment that sells the work.
4. **When risk-management fires (3 minutes in):** "Now the risk manager consolidates the six signals. It's not voting — it's weighting based on conviction and consistency."
5. **When portfolio-manager fires (final 30 seconds):** "Final node. This is the decision: position size, side, rationale. Cite-able. Auditable. Every signal that fed into this is queryable."

---

## The crash-recovery moment (90 seconds — optional but powerful)

This is the line that closes technical buyers.

> "Watch this. I'm going to crash the process mid-run."

Open a second tab. Start a new run. Wait until the third analyst node fires. **Kill the server process** (`kill -9` is fine — that's the point).

> "If this were a chatbot, the conversation is gone. We just lost three minutes of work. But this workflow checkpoints to disk after every node. Let me restart the server."

Restart. Resume the same `thread_id` via the run config.

> "We didn't re-run those three analysts. State picked up where it stopped. In production, this is the difference between a system that gets used and one that gets abandoned the first time it falls over."

---

## Close (60 seconds)

> "Three things I want to point out before questions:
>
> 1. **This is your stack.** Pgvector, FastAPI, SQLite — nothing here is locked to a vendor. The model layer is an interface. Tomorrow's model lands, we swap it; the workflow doesn't care.
>
> 2. **You saw analyst signals.** What you didn't see: every prompt, every retry, every token. All of it is captured. You'll never wonder why the system said what it said.
>
> 3. **This is one workflow.** We pick six analyst lenses for the earnings scenario because that's the scenario. For your business — supplier vetting, contract review, customer-onboarding QA — the lenses change but the architecture is identical."

Pause. Look at the camera.

> "Where would you want this pointed first?"

That's the qualifying question. Let them talk.

---

## Common buyer questions and answers

**"Can it run on our infrastructure?"**
Yes. The whole thing is Python + SQLite. Self-hostable behind your firewall. No data leaves your environment if you don't want it to.

**"How long to ship something like this for us?"**
The first capability pilot is four to six weeks. We start from a working baseline like the one you just saw and tailor the analyst lenses, the data sources, and the decision logic to your domain.

**"How do you charge?"**
Capability Pilot is fixed-fee. Indicative range shared after we scope the work. We don't bill hourly — slow delivery shouldn't be rewarded.

**"What if your model vendor changes pricing or shuts down?"**
The model layer is an interface. We've already tested swaps between Anthropic, OpenAI, and local models. The eval harness (capability 03) verifies behaviour stays correct after a swap. This is not a retrofit; it's built in from day one.

**"What happens to our data after the demo?"**
Default retention is seven days. After that, an automated scrub deletes the workspace. Audit log is kept for 12 months. Full handling rules in [`docs/decisions/ADR-006-...md`](decisions/ADR-006-earnings-reaction-playbook-and-claude-sdk-comparison.md) and the Prudentia [demo-data policy](https://prudentiadigital.co.za/docs/sales/demo-data-handling.md).

---

## Fallback when the live demo fails

If anything fails — network drops, API quota hit, demo machine asleep:

1. **Acknowledge it immediately.** "The live system is having a moment — happens 1 in 30 demos. Let me show you the recording I prepared."
2. **Open `assets/demos/earnings-reaction-playbook.mp4`** (5-minute pre-recorded run). Narrate live over it using the same script as above.
3. **Do not try to fix the live system on screen.** It looks worse than the recording.
4. **After the call**, log the failure in the demo-ops journal with root-cause hypothesis. If the same failure recurs twice in a month, the live demo path is unreliable — switch to recording-first until fixed.

---

## After the call

- **Within 1 hour:** send the one-pager PDF and a follow-up email referencing the specific workflow scenario the prospect named.
- **Within 24 hours:** counter-signed NDA if confidential data was discussed.
- **Within 7 days:** the demo-data scrub script runs automatically; verify the audit log entry for this prospect.

---

## Maintenance

This script is rehearsed at minimum once per quarter. After any of the following, rehearse before the next live demo:

- New analyst added to `EARNINGS_REACTION_ANALYSTS`
- Model provider change
- `langgraph` version bump
- Any change to the streaming UI

The rehearsal is timed end-to-end. If it goes over 8 minutes, the script is wrong, not the demo.
