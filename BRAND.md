# Brand: The Bench

This document defines the identity of this system. It is the single source of truth for name, voice, visual language, and story. No external references; the brand stands on its own.

---

## The Name

**The Bench** is the name of the system.

- **What it is:** The committee. The second opinion. The bar. Eighteen analyst agents plus risk and portfolio management, convened to pressure-test conviction before it becomes position.
- **What it does:** Takes tickers, runs them through the committee, returns BUY/SELL/HOLD with reasoning. Holds the benchmark. Measures what matters.
- **What it is not:** Not the thesis. Not the researcher. Not the architect. The Bench is the court that evaluates what the thesis proposes.

Use **"The Bench"** in headlines and key copy. Use **"the Bench"** in running text. The repo and product may still be called "AI Hedge Fund" in code and URLs; the *character* and *brand* are The Bench.

---

## The Story

**Two roles.**

One holds the thesis. Reads SOUL, builds sleeves, defines what the portfolio is supposed to do. That role is the researcher.

The Bench holds the bar. It does not draft the thesis. It takes the same names the thesis proposes and runs them through eighteen minds: value, growth, momentum, risk. It challenges. It disagrees. It forces conviction to earn its place.

**The only measure that matters is beating the bar.** The researcher proposes; the Bench judges. When they agree, confidence rises. When they disagree, the gap is the signal.

So the main character of this story is **The Bench** — the committee, the standard, the second opinion. Not the origin of the thesis, but the place where the thesis is tested.

---

## Voice & Tone

- **Authoritative but not arrogant.** The Bench states what it sees. It does not oversell or hedge with fluff.
- **Precision over volume.** Short sentences. No filler. Every line carries weight.
- **Engineering, not marketing.** Specs over slogans. Results over promises.
- **Calm.** No hype, no fear, no FOMO. The Bench is steady.

### Voice traits

| Trait | Do | Don't |
|-------|----|-------|
| Clarity | One idea per sentence. Subject-verb-object. | Long paragraphs. Jargon without definition. |
| Confidence | State the bar. State the result. | "Maybe," "we believe," "hopefully." |
| Restraint | Let numbers and structure speak. | Exclamation points. Superlatives. |
| Consistency | Same terms everywhere (benchmark, bar, committee, signal). | Invent new words for the same idea. |

---

## Taglines & Key Phrases

These are the approved lines. Use them in docs, CLI output, and UI.

### Primary

- **The benchmark. No substitute.**  
  The bar is the bar. There is nothing to swap in.

- **The only measure that matters is beating it.**  
  Alpha vs benchmark. Everything else is noise.

- **Precision. No noise. Just the signal.**  
  What the system optimizes for: clean input, clean output.

- **Simple. Powerful. Different.**  
  Three words. No fluff. What the Bench is.

### Secondary

- **Not a toy. Not a dashboard.**  
  Full system. Real research. Real risk.

- **The committee holds the bar.**  
  Eighteen minds. One standard.

- **Conviction gets challenged before it gets trusted.**  
  Role of the second opinion.

- **One mutable file. Everything else is the harness.**  
  (Autoresearch.) Clean attribution. No magic.

Use primary taglines in banners and hero copy. Use secondary in sections and callouts. Do not invent new taglines without adding them here.

---

## Visual Language

The Bench has a defined look. Same family as the voice: precise, structured, no clutter.

### ASCII & typography

- **Block letters** for titles and key names (e.g. RELATIVE STRENGTH, RUNBOOK, SOUL). Uppercase, spaced. One concept per banner.
- **Box-drawing** for structure: `╔ ║ ╚ ═ ╭ ╮ ╰ ╯ ┬ ┴ ├ ┤ │ ─`. Use for banners, tables, and callouts.
- **Code blocks** for commands and data. Monospace. No decorative borders inside the block.

### Layout

- **Banners:** One banner per doc or major section. Content: block-letter title + one primary tagline + one short line. No more.
- **Callouts:** Short lines in a single box. One idea. Example:  
  `╭─────────────────────────────────────────╮`  
  `│  One mutable file. Everything else is the harness.  │`  
  `╰─────────────────────────────────────────╯`
- **Tables:** Header row, then data. Align numbers. No emoji in tables unless the column is explicitly "status" or "flag."

### Color (CLI / UI)

- **Green** for positive (alpha, returns above bar, success).
- **Red** for negative (below bar, loss, failure).
- **Dim** for metadata (dates, labels, secondary info).
- **Bold** for the one thing that matters in a line (e.g. strategy name, Sharpe).

Use color to support scanning. Do not use color as decoration.

---

## Personality

The Bench behaves like a single character in the story.

| Dimension | The Bench is … | The Bench is not … |
|-----------|----------------|---------------------|
| Role | The judge. The bar. The committee. | The author of the thesis. The portfolio architect. |
| Temperament | Calm. Precise. Unimpressed by hype. | Anxious. Salesy. Apologetic. |
| Relationship to the researcher | Respectful but independent. Tests, does not obey. | Subordinate. Or hostile. |
| Relationship to the user | Clear. Direct. "Here is the bar. Here is the result." | Vague. Over-explaining. Patronizing. |

When we write as "the Bench" or "the system," we use this personality. Docs and CLI copy should feel like the Bench speaking.

---

## Naming Conventions

| Concept | Preferred term | Avoid |
|---------|----------------|-------|
| The system (this repo / product as a character) | The Bench | AI Hedge Fund (in brand copy), "the tool" |
| The 18 agents together | The committee | The agents, the models |
| The bar to clear | The benchmark, the bar | The target, the goal (unless in a technical sense) |
| Outperformance vs benchmark | Alpha, beating the bar | Beating the market (vague) |
| The thesis-driven side | The researcher, the thesis | (Do not name the other system in Bench brand copy unless linking.) |
| Tuning / optimization loop | Autoresearch | Auto-research, self-tuning |
| Risk-adjusted return | Sharpe, Sortino | (Use standard terms.) |

In code and config, existing names (e.g. `ai-hedge-fund`, `cache_signals`) stay. In user-facing copy and BRAND.md, prefer the terms above.

---

## Do's and Don'ts

### Do

- Lead with the bar and the result.
- Use the approved taglines in banners and key sections.
- Keep sentences short. One idea per line when it helps.
- Use block letters and box-drawing for structure, not decoration.
- Refer to "The Bench" or "the Bench" when we mean the character/system.
- Let the researcher be the researcher; the Bench is the judge.

### Don't

- Reference other brands (no names of other companies or products) in taglines or voice.
- Invent new taglines without documenting them in BRAND.md.
- Use hype, exclamation points, or vague superlatives.
- Mix voice: either the Bench speaks (authoritative, precise) or we state facts neutrally.
- Name the thesis-holder in Bench hero copy; we can link elsewhere for that.

---

## Summary

| Item | Definition |
|------|------------|
| **Name** | The Bench |
| **Role** | Second opinion. Committee. The bar. |
| **Story** | The researcher proposes; the Bench judges. Conviction is challenged before it is trusted. |
| **Voice** | Authoritative, precise, engineering, calm. |
| **Look** | Block letters, box-drawing, clear tables, restrained color. |
| **Taglines** | The benchmark. No substitute. / The only measure that matters is beating it. / Precision. No noise. Just the signal. / Simple. Powerful. Different. |

This is the brand. Use it everywhere the Bench speaks.
