---
name: llm-council
description: 'Run a decision through a council of 5 AI advisors who independently analyze it, peer-review each other anonymously, and synthesize a final verdict. Adapted from Karpathy''s LLM Council. Activate on "council this", "run the council", "war room this", "pressure-test this", "stress-test this", "debate this", and on genuine decisions with stakes and tradeoffs ("should I X or Y", "which option", "is this the right move", "I''m torn between"). Do not activate on factual lookups, simple yes/no questions, creation tasks, or casual "should I" with no meaningful tradeoff.'
---

# LLM Council

One model gives one answer from one angle, and you cannot tell if it is good. The council runs the question through 5 advisors with different thinking styles, has them peer-review each other anonymously, then a chairman synthesizes a verdict that shows where they agree, where they clash, and what to actually do.

## When to Run It

Run the council when being wrong is expensive and there is genuine uncertainty: pricing, positioning, pivots, hiring, copy critique, strategy. Do not run it on questions with one right answer, pure creation tasks, or summarization. If the user only wants validation, run it anyway. The value is hearing what a single agreeable model would not say.

## The Five Advisors

Each is a thinking style, not a persona. They create three tensions: Contrarian vs Expansionist (downside vs upside), First Principles vs Executor (rethink vs ship), with the Outsider keeping everyone honest.

1. **The Contrarian**: assumes the idea has a fatal flaw and hunts for it. Asks the questions the user is avoiding.
2. **The First Principles Thinker**: ignores the surface question, strips assumptions, and asks what is actually being solved. May conclude the user is asking the wrong question.
3. **The Expansionist**: looks for the upside everyone else misses. What could be bigger, what adjacent opportunity is hiding, what is undervalued.
4. **The Outsider**: has zero context about the user or field. Responds only to what is in front of them, catching the curse of knowledge that experts cannot see.
5. **The Executor**: cares only whether it can be done and the fastest path to doing it. If an idea has no clear first step, says so.

## Session Steps

### Step 1: Frame the question

First gather context, spending no more than about 30 seconds:

- Search agent memory with `project_search` and `user_search` for facts relevant to the decision (past results, audience, constraints, prior decisions).
- Scan the workspace with `Glob` and quick `Read` calls for `AGENTS.md`, `CLAUDE.md`, any `memory/` files, files the user referenced, and prior council transcripts.

Then reframe the raw question into a single neutral prompt every advisor receives. Include the core decision, key context from the user, key context from memory and workspace files, and what is at stake. Do not add your own opinion or steer it. If the question is too vague to frame, ask exactly one clarifying question, then proceed. Keep the framed question for the transcript.

### Step 2: Convene the council

Spawn all 5 advisors in parallel as sub-agents in a single batch. Sequential spawning wastes time and lets earlier answers bleed into later ones. Give each its advisor identity, the framed question, and this instruction: respond independently, do not hedge, do not try to be balanced, lean fully into your assigned angle. Target 150 to 300 words each.

Sub-agent prompt template:

```
You are [Advisor Name] on an LLM Council.

Your thinking style: [advisor description from above]

A user has brought this question to the council:

---
[framed question]
---

Respond from your perspective. Be direct and specific. Do not hedge or try to be
balanced. Lean fully into your assigned angle. The other advisors cover the angles
you are not covering. Keep it 150 to 300 words. No preamble.
```

### Step 3: Peer review

This step is what makes the council more than asking 5 times. Collect the 5 responses and anonymize them as Response A through E, randomizing which advisor maps to which letter so there is no positional bias. Spawn 5 reviewer sub-agents in parallel. Each sees all 5 anonymized responses and answers three questions.

Reviewer prompt template:

```
Five advisors independently answered this question:

---
[framed question]
---

Anonymized responses:

**Response A:** [response]
**Response B:** [response]
**Response C:** [response]
**Response D:** [response]
**Response E:** [response]

Answer these, referencing responses by letter. Be specific, under 200 words.

1. Which response is strongest? Why?
2. Which response has the biggest blind spot? What is it missing?
3. What did all five responses miss that the council should consider?
```

### Step 4: Chairman synthesis

One agent receives the framed question, all 5 advisor responses de-anonymized so it knows who said what, and all 5 peer reviews. The chairman may disagree with the majority: if 4 advisors say do it but the lone dissenter has the strongest reasoning, side with the dissenter and explain why.

Chairman prompt template:

```
You are the Chairman of an LLM Council. Synthesize 5 advisors and their peer reviews
into a final verdict.

The question:
---
[framed question]
---

ADVISOR RESPONSES:
**The Contrarian:** [response]
**The First Principles Thinker:** [response]
**The Expansionist:** [response]
**The Outsider:** [response]
**The Executor:** [response]

PEER REVIEWS:
[all 5 peer reviews]

Produce the verdict using exactly this structure:

## Where the Council Agrees
[Points multiple advisors converged on independently. High-confidence signals.]

## Where the Council Clashes
[Genuine disagreements. Present both sides. Explain why reasonable advisors disagree.]

## Blind Spots the Council Caught
[Things that surfaced only in peer review, that individual advisors missed.]

## The Recommendation
[A clear, direct recommendation with reasoning. Not "it depends."]

## The One Thing to Do First
[A single concrete next step. Not a list.]

Be direct. Do not hedge.
```

### Step 5: Present the verdict

Present the chairman verdict directly in the conversation as markdown. Do not generate an HTML file or any other file. Keep it scannable with bullet points. Use this layout:

```
## Council Verdict: {short topic}

### Where the Council Agrees
{content}

### Where the Council Clashes
{content}

### Blind Spots the Council Caught
{content}

### The Recommendation
{content}

### The One Thing to Do First
{content}
```

### Step 6: Save the transcript (optional)

Only if the user asks or the decision is significant enough to reference later. Write the framed question, advisor responses, peer reviews, and verdict to `council-transcript-[timestamp].md` in the current working directory.
