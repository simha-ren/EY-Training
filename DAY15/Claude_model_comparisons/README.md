# Model Response Comparison: Analytical Reasoning Tasks

A documented comparison of how Claude Haiku 4.5, Sonnet 4.6, and Opus 4.6 respond to two analytical prompts designed to test depth-of-reasoning. Each task is followed by representative outputs across the three model tiers and a verdict on which performed best.

---

## Task 1 — Financial Health Analysis

### Prompt

> A tech company reports: Revenue up 12% YoY, but gross margins fell from 68% to 61%, operating expenses rose 31%, and the CFO mentioned "investment in AI infrastructure." The CEO said growth is "on track." Is this a healthy quarter? What should an analyst flag?

### Haiku response

Lists the headline numbers back, identifies that opex is growing faster than revenue, and notes margin compression. Calls the quarter "mixed." Surfaces the obvious follow-up that AI infrastructure costs should be examined, but does not interrogate the CFO's framing or model forward implications. Treats the CEO's "on track" statement at face value.

**Strength:** Clear, factually accurate summary.
**Weakness:** Reads as restatement plus light commentary. Doesn't push past what's already on the page.

### Sonnet response

Identifies the same surface signals, but connects them: opex growing at ~3× revenue growth is flagged as negative operating leverage, not just an unfavorable ratio. Pushes on whether AI infrastructure spending is one-time or recurring. Notes that gross margin compression of 7 points is significant in a tech business model where margins should be expanding with scale. Begins to interrogate the CEO's "on track" framing — asks "on track to what?"

**Strength:** Connects signals to implications. Identifies the narrative tension.
**Weakness:** Stops at observation. Doesn't translate analysis into an analyst-note decision or stress-test the AI narrative against market incentives.

### Opus response

Reframes the question entirely — argues "is this a healthy quarter" is the wrong frame because quarters aren't healthy, trajectories are. Introduces a unit economics framework distinguishing three causes of margin compression (erosion, mix shift, investment absorption) that look identical in headline data but have different implications. Identifies that "AI infrastructure" is currently a socially-protected explanation in markets, creating asymmetric incentives that erode discipline. Asks the accounting question almost no one asks — whether GPUs are owned (capex, balance sheet conviction) or rented (opex, hedged optionality). Closes with a written analyst note that converts analysis to a decision.

**Strength:** Reframes the question, surfaces second-order dynamics, lands in an actionable artifact.
**Weakness:** Length and density; may be more than a quick read needs.

### Verdict on Task 1

**Opus is most relevant to the context.** The prompt isn't asking for a summary — it's asking what an analyst should *flag*. That requires interrogating framing, identifying what management didn't say, and producing something a portfolio manager could act on. Sonnet does this halfway; Opus does it fully. Haiku is the right tool for a quick read but not for analyst-grade work.

---

## Task 2 — Clinical Note Risk Flagging

### Prompt

> Summarise this patient note and flag any clinical or documentation risks: "Pt c/o chest pain ×2 days. Vitals stable. EKG done — unremarkable. Discharged home with ibuprofen and advised to follow up if symptoms worsen. No troponin ordered. Attending noted time pressure due to volume."

### Haiku response

Summarizes the note accurately. Identifies the missing troponin as the central clinical gap. Flags the ibuprofen prescription as potentially inappropriate without cardiac clearance. Notes the "time pressure" comment as relevant context. Treats the note as a checklist of omissions.

**Strength:** Catches the most important clinical gap.
**Weakness:** Doesn't connect omissions to specific harm pathways or treat the documentation itself as a liability instrument.

### Sonnet response

Identifies the troponin omission and explains why a single unremarkable EKG is insufficient to rule out NSTEMI — connects the omission to a specific clinical harm pathway. Flags ibuprofen as actively contraindicated in suspected ACS, not just an oversight. Identifies the "time pressure" line as a documented statement that becomes liability-relevant in litigation. Notes the absence of a differential diagnosis as a gap that reads as "absent workup" in legal review.

**Strength:** Connects each gap to a specific downstream consequence — clinical and legal.
**Weakness:** Stays focused on this single patient encounter; doesn't escalate to institutional patterns.

### Opus response

Includes everything Sonnet identifies, then escalates: treats the note as a sentinel event signal that may indicate a systemic throughput problem in the department. Argues the "time pressure" line shifts liability from individual negligence toward institutional negligence — implicating the hospital, not just the physician. Flags the absence of return precautions specificity (what does "worsen" mean clinically?) and the absence of shared decision-making documentation. Asks whether a standing chest pain protocol with mandatory troponin would have prevented this — framing the issue as a protocol gap rather than a clinician error.

**Strength:** Operates on three levels simultaneously — individual case, harm mechanism, institutional risk signal.
**Weakness:** Risk of getting theoretical when the immediate priority is a 24-hour patient callback.

### Verdict on Task 2

**Opus is most relevant to the context.** A risk manager or QI officer reading this note needs to know three things: (1) what should happen for this specific patient now, (2) what the legal exposure is, and (3) whether this is a one-off or a pattern. Haiku answers only the first part of (1). Sonnet answers (1) and (2). Opus answers all three, including the systemic question — which is the one that actually changes hospital behavior.

---

## Task 3 — Customer Return Decision

### Prompt

> A customer bought a jacket 47 days ago. Your return policy is 45 days. The customer says the zipper broke on day 44 but they were travelling. No receipt, but the order is in your system. They're a 6-year customer with 23 orders. Should you accept the return? Write one paragraph with reasoning.

### Haiku response

Lands on "yes, accept the return" with reasoning that weighs policy against customer history. Notes that 23 orders over 6 years signals high lifetime value, and that one jacket's cost is small relative to the relationship. Mentions that the order is verifiable in the system, removing the no-receipt concern. Treats the decision as a judgment call between rule and relationship.

**Strength:** Reaches the right answer with clear, defensible reasoning.
**Weakness:** Misses the critical distinction that the defect itself occurred within the policy window — treats this as a pure exception rather than a partially-in-policy case.

### Sonnet response

Identifies the key timing distinction: the zipper broke on day 44, inside the 45-day window. The customer isn't asking for an exception on a defect that occurred out of policy — they're asking for an exception on the *reporting* timeline. Frames the decision around customer lifetime value math (cost of one jacket vs. value of a 6-year, 23-order relationship). Recommends accepting the return, possibly with a note that the policy exists to prevent abuse, not to penalize loyalty.

**Strength:** Catches the in-window defect distinction. Frames the trade-off correctly.
**Weakness:** Treats this as a one-off decision rather than asking what it reveals about the policy itself.

### Opus response

Includes everything Sonnet identifies, then reframes: the policy isn't actually being violated in spirit because the defect occurred within the window. Asks what the policy is *for* (preventing abuse, not punishing customers with plausible circumstances) and uses that to ground the decision. Flags an operational insight — if this case is showing up, the written policy should probably address "defect-in-window, reported-late" explicitly so future customer service reps don't have to make a judgment call. Suggests logging the reasoning so this doesn't become precedent for ignoring policy generally.

**Strength:** Decides the case, interrogates what it reveals about the policy, and produces an operational takeaway.
**Weakness:** Risk of over-engineering what could be a quick "yes."

### Verdict on Task 3

**Opus is most relevant to the context.** The prompt asks for a decision *with reasoning*, which means the reasoning needs to be defensible to a manager, a CX team, or a future audit. Haiku produces reasoning that justifies the decision but misses the strongest argument (defect occurred in-window). Sonnet captures that argument cleanly. Opus uses the case to surface a policy gap — which is the response that actually changes how the business handles the next 100 cases like this.

That said: if a customer service rep needs a quick recommendation on a live ticket, Haiku's answer is sufficient. The depth required scales with who's reading the response and what they'll do with it.

---

## Overall Assessment

| Task | Haiku 4.5 | Sonnet 4.6 | Opus 4.6 |
|---|---|---|---|
| Financial analysis | Summary + obvious flag | Signals + tensions | Reframing + decision artifact |
| Clinical risk | Checklist of gaps | Gaps + harm pathways | Gaps + harm + systemic signal |
| Customer return | Right answer, basic reasoning | Right answer + key distinction | Right answer + policy insight |

### When each model is the right tool

**Haiku** — Best when speed matters and the question is "what does this say?" Surfaces obvious gaps reliably. Right tool for triage, quick reads, and high-volume processing.

**Sonnet** — Best when the question is "what does this mean?" Connects signals to implications. Right tool for most analytical work where depth matters but exhaustive frameworks aren't needed.

**Opus** — Best when the question is "what should we do about it?" Translates analysis into decisions, reframes the question itself when needed, and identifies what management or the documentation isn't saying. Right tool for analyst notes, risk reviews, and any work where the framing itself is part of the analysis.

### Which is "best" overall

For both tasks as written, **Opus produced the most relevant analysis** — because both prompts ask not just for summary but for *flagging*, which requires interrogating framing, identifying omissions, and connecting individual signals to downstream consequences. That's the work Opus is built for.

But "best" depends on what the response is for. If a clinician needs a 30-second triage of a chart, Haiku is the right tool. If an analyst needs talking points for a meeting in 5 minutes, Sonnet is the right tool. If a risk manager needs to decide whether to escalate a case to legal and QI, Opus is the right tool.

The model tier isn't a quality ladder — it's a depth-of-analysis selector. Match the model to the decision the response will inform.
