"""
Build a Substack-ready markdown outline from a second-opinion run result.

Example:
    poetry run python scripts/second_opinion_to_substack_outline.py \
      --run-result second_opinion_runs/second_opinion_run_result_14.json \
      --portfolio-draft portfolio_draft_tastytrade_full.json
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from statistics import mean
from typing import Any


def _safe_float(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _stance(decision: dict[str, Any]) -> str:
    raw = decision.get("action") or decision.get("decision") or decision.get("stance") or "hold"
    return str(raw).upper()


def _weight_map(draft: dict[str, Any]) -> dict[str, float]:
    out: dict[str, float] = {}
    for asset in draft.get("assets", []) or []:
        symbol = str(asset.get("symbol", "")).upper()
        if not symbol:
            continue
        out[symbol] = float(asset.get("target_weight_pct", 0.0) or 0.0)
    return out


def _bucket(symbol: str, stance: str, weight: float) -> str:
    # Same heuristic family as second_opinion_report.py
    if weight >= 0:
        if stance in ("BUY", "HOLD"):
            return "strong_agree"
        if stance in ("SELL", "SHORT"):
            return "hard_disagree" if weight >= 3.0 else "mild_disagree"
    else:
        if stance in ("SELL", "SHORT"):
            return "strong_agree"
        if stance in ("BUY", "HOLD"):
            return "hard_disagree" if abs(weight) >= 3.0 else "mild_disagree"
    return "mild_disagree"


def _tokenize_reason(text: str) -> list[str]:
    cleaned = re.sub(r"[^a-zA-Z0-9\s]", " ", text.lower())
    return [t for t in cleaned.split() if len(t) >= 4]


def _theme_counts(reason_texts: list[str]) -> Counter[str]:
    themes = {
        "valuation_stretch": ("valuation", "expensive", "overvalued", "multiple", "p/e", "p/s", "p/b"),
        "sentiment_weak": ("sentiment", "negative", "weak", "bearish"),
        "regime_risk": ("regime", "risk", "cut", "reduce"),
        "fundamental_softness": ("fundamental", "growth", "margin", "earnings", "revenue"),
        "insider_pressure": ("insider", "selling", "sellers"),
    }
    scores: Counter[str] = Counter()
    for txt in reason_texts:
        toks = set(_tokenize_reason(txt))
        for theme, words in themes.items():
            if any(w.lower() in toks for w in words):
                scores[theme] += 1
    return scores


def _top_bearish_agents(
    analyst_signals: dict[str, Any], symbols: list[str], n: int = 4
) -> dict[str, list[tuple[str, float]]]:
    out: dict[str, list[tuple[str, float]]] = {}
    for symbol in symbols:
        rows: list[tuple[str, float]] = []
        for agent, payload in analyst_signals.items():
            if not isinstance(payload, dict):
                continue
            signal_blob = payload.get(symbol)
            if not isinstance(signal_blob, dict):
                continue
            signal = str(signal_blob.get("signal", "")).lower()
            conf = _safe_float(signal_blob.get("confidence")) or 0.0
            if signal == "bearish":
                rows.append((agent, conf))
        rows.sort(key=lambda x: x[1], reverse=True)
        out[symbol] = rows[:n]
    return out


def _bench_banner() -> list[str]:
    return [
        "> The benchmark. No substitute.",
        "> The only measure that matters is beating the bar.",
        "",
    ]


def _bench_title(sleeve: str, run_id: Any, short_count: int, buy_count: int) -> str:
    if short_count > 0 and buy_count == 0:
        return f"The Bench vs {sleeve}: A full-risk rejection (Run {run_id})"
    return f"The Bench vs {sleeve}: Thesis under pressure (Run {run_id})"


def build_outline(
    run_result: dict[str, Any],
    draft: dict[str, Any],
    title: str | None = None,
    voice: str = "bench",
) -> str:
    run_id = run_result.get("run_id")
    status = run_result.get("status")
    results = run_result.get("results") or {}
    decisions = results.get("decisions") or {}
    analyst_signals = results.get("analyst_signals") or {}
    meta = results.get("meta") or {}
    sleeve = draft.get("sleeve") or meta.get("sleeve") or "-"
    params_profile = draft.get("params_profile") or meta.get("params_profile") or "-"

    weights = _weight_map(draft)
    rows: list[dict[str, Any]] = []
    for symbol, decision in decisions.items():
        stance = _stance(decision)
        conf = _safe_float(decision.get("confidence"))
        reasoning = str(decision.get("reasoning") or "").strip()
        w = float(weights.get(symbol, 0.0))
        rows.append(
            {
                "symbol": symbol,
                "stance": stance,
                "confidence": conf,
                "weight": w,
                "bucket": _bucket(symbol, stance, w),
                "reasoning": reasoning,
            }
        )

    stance_counts = Counter(r["stance"] for r in rows)
    conf_values = [r["confidence"] for r in rows if isinstance(r["confidence"], float)]
    avg_conf = mean(conf_values) if conf_values else 0.0
    theme_counts = _theme_counts([r["reasoning"] for r in rows if r["reasoning"]])
    top_themes = ", ".join([f"{k} ({v})" for k, v in theme_counts.most_common(3)]) or "n/a"

    hard = [r for r in rows if r["bucket"] == "hard_disagree"]
    mild = [r for r in rows if r["bucket"] == "mild_disagree"]
    agree = [r for r in rows if r["bucket"] == "strong_agree"]
    top_bears = _top_bearish_agents(analyst_signals, [r["symbol"] for r in hard[:8]])

    short_count = stance_counts.get("SHORT", 0)
    buy_count = stance_counts.get("BUY", 0)
    neutral_title = (
        f"{sleeve}: Thesis vs Committee - Run {run_id} "
        f"({short_count} SHORT, {buy_count} BUY)"
    )
    suggested_title = title or (
        _bench_title(str(sleeve), run_id, short_count, buy_count)
        if voice == "bench"
        else neutral_title
    )

    lines: list[str] = []
    lines.append(f"# {suggested_title}")
    lines.append("")
    if voice == "bench":
        lines.extend(_bench_banner())
    lines.append("## TL;DR")
    lines.append(
        f"- Run `{run_id}` finished with status `{status}` for sleeve `{sleeve}` (`params_profile={params_profile}`)."
    )
    lines.append(
        f"- Committee stance mix: "
        f"{', '.join([f'{k}={v}' for k, v in stance_counts.items()]) or 'none'}."
    )
    lines.append(
        f"- Agreement buckets: strong agree={len(agree)}, mild disagree={len(mild)}, hard disagree={len(hard)}."
    )
    lines.append(f"- Average confidence: {avg_conf:.1f}. Dominant reason themes: {top_themes}.")
    lines.append("")

    if voice == "bench":
        lines.append("## Part I: The setup")
        lines.append(f"- The researcher proposed the `{sleeve}` sleeve.")
        lines.append("- The Bench ran the same names through the committee and held the bar.")
    else:
        lines.append("## 1) Thesis Context")
        lines.append(
            f"- Sleeve mission: `{sleeve}` (from `SOUL.md`) and proposed sizing from Dexter draft."
        )
        lines.append(
            "- This note evaluates where the AIHF committee confirms the thesis vs where it rejects current sizing."
        )
    lines.append("")

    lines.append("## Part II: The verdict table" if voice == "bench" else "## 2) Committee Verdict Snapshot")
    lines.append("| Symbol | Target Weight | Committee Stance | Confidence | Bucket |")
    lines.append("|---|---:|---|---:|---|")
    for r in sorted(rows, key=lambda x: -abs(x["weight"])):
        conf = f"{r['confidence']:.1f}" if isinstance(r["confidence"], float) else "-"
        lines.append(
            f"| {r['symbol']} | {r['weight']:.1f}% | {r['stance']} | {conf} | {r['bucket']} |"
        )
    lines.append("")

    lines.append("## Part III: Why the committee leaned bearish" if voice == "bench" else "## 3) Why the Committee Is Leaning This Way")
    lines.append("- Repeated themes from portfolio-manager reasoning strings:")
    for theme, count in theme_counts.most_common(5):
        lines.append(f"  - `{theme}` appears in {count} ticker-level rationales.")
    if not theme_counts:
        lines.append("  - No dominant theme extracted.")
    lines.append("")

    lines.append("## Part IV: Hard-disagree names" if voice == "bench" else "## 4) Hard-Disagree Deep Dive")
    if not hard:
        lines.append("- No hard disagreements this run.")
    else:
        for r in sorted(hard, key=lambda x: -abs(x["weight"])):
            lines.append(
                f"- **{r['symbol']} ({r['weight']:.1f}%)** -> `{r['stance']}` ({r['confidence'] or '-'} conf)"
            )
            if r["reasoning"]:
                lines.append(f"  - PM rationale: {r['reasoning']}")
            bears = top_bears.get(r["symbol"], [])
            if bears:
                bear_txt = ", ".join([f"{a} ({c:.0f})" for a, c in bears])
                lines.append(f"  - Top bearish agents: {bear_txt}")
    lines.append("")

    lines.append("## Part V: Portfolio action plan" if voice == "bench" else "## 5) Portfolio Action Plan (Draft)")
    if voice == "bench":
        lines.append("- Do not argue with a full committee rejection. Resize first.")
        lines.append("- Keep thesis structure. Cut expression risk.")
        lines.append("- Re-run after weight edits. The delta is the signal.")
    else:
        lines.append("- Keep or increase names where thesis and committee strongly agree.")
        lines.append("- For hard disagreements:")
        lines.append("  - cut target size,")
        lines.append("  - defer entries pending confirmation, or")
        lines.append("  - replace with same-sleeve alternatives that preserve thesis intent.")
        lines.append("- Re-run second-opinion after weight edits and compare bucket deltas.")
    lines.append("")

    lines.append("## Part VI: Next experiment before rebalance" if voice == "bench" else "## 6) Next Experiment Before Rebalance")
    lines.append("- Run the same sleeve under two profiles:")
    lines.append("  - `params_profile=..._baseline`")
    lines.append("  - `params_profile=..._factors_on`")
    lines.append("- Promote only changes that survive both committee disagreement and backtest evidence.")
    lines.append("")

    lines.append("---")
    lines.append("Generated by `scripts/second_opinion_to_substack_outline.py`.")
    return "\n".join(lines) + "\n"


def build_final_draft(
    run_result: dict[str, Any],
    draft: dict[str, Any],
    title: str | None = None,
    voice: str = "bench",
) -> str:
    run_id = run_result.get("run_id")
    status = run_result.get("status")
    results = run_result.get("results") or {}
    decisions = results.get("decisions") or {}
    analyst_signals = results.get("analyst_signals") or {}
    meta = results.get("meta") or {}
    sleeve = draft.get("sleeve") or meta.get("sleeve") or "-"
    params_profile = draft.get("params_profile") or meta.get("params_profile") or "-"

    weights = _weight_map(draft)
    rows: list[dict[str, Any]] = []
    for symbol, decision in decisions.items():
        stance = _stance(decision)
        conf = _safe_float(decision.get("confidence"))
        reasoning = str(decision.get("reasoning") or "").strip()
        w = float(weights.get(symbol, 0.0))
        rows.append(
            {
                "symbol": symbol,
                "stance": stance,
                "confidence": conf,
                "weight": w,
                "bucket": _bucket(symbol, stance, w),
                "reasoning": reasoning,
            }
        )

    stance_counts = Counter(r["stance"] for r in rows)
    short_count = stance_counts.get("SHORT", 0)
    buy_count = stance_counts.get("BUY", 0)
    hold_count = stance_counts.get("HOLD", 0)
    conf_values = [r["confidence"] for r in rows if isinstance(r["confidence"], float)]
    avg_conf = mean(conf_values) if conf_values else 0.0
    hard = [r for r in rows if r["bucket"] == "hard_disagree"]
    mild = [r for r in rows if r["bucket"] == "mild_disagree"]
    agree = [r for r in rows if r["bucket"] == "strong_agree"]
    theme_counts = _theme_counts([r["reasoning"] for r in rows if r["reasoning"]])
    top_themes = [k for k, _ in theme_counts.most_common(3)]
    top_bears = _top_bearish_agents(analyst_signals, [r["symbol"] for r in hard[:10]])

    if voice == "bench":
        suggested_title = title or _bench_title(str(sleeve), run_id, short_count, buy_count)
    else:
        suggested_title = title or f"{sleeve}: Committee readout (Run {run_id})"

    lines: list[str] = []
    lines.append(f"# {suggested_title}")
    lines.append("")
    if voice == "bench":
        lines.extend(_bench_banner())

    # Intro hook paragraph
    if voice == "bench":
        lines.append(
            f"The researcher proposed `{sleeve}`. The Bench ran the same names through the committee. "
            f"Result: `{short_count}` SHORT, `{buy_count}` BUY, `{hold_count}` HOLD. "
            f"When the bar rejects the whole sleeve expression, the signal is not subtle."
        )
    else:
        lines.append(
            f"This memo summarizes run `{run_id}` for sleeve `{sleeve}` (`params_profile={params_profile}`), "
            f"including where committee stance and target sizing diverged."
        )
    lines.append("")

    lines.append("## Executive summary")
    lines.append(f"- Run status: `{status}`")
    lines.append(f"- Params profile: `{params_profile}`")
    lines.append(
        f"- Committee mix: SHORT={short_count}, BUY={buy_count}, HOLD={hold_count}"
    )
    lines.append(
        f"- Disagreement buckets: strong agree={len(agree)}, mild disagree={len(mild)}, hard disagree={len(hard)}"
    )
    lines.append(f"- Average confidence: {avg_conf:.1f}")
    if top_themes:
        lines.append(f"- Dominant reason themes: {', '.join(top_themes)}")
    lines.append("")

    lines.append("## What changed in conviction")
    if hard:
        lines.append(
            "The key update is concentration of disagreement: high-weight names are being rejected by the committee, "
            "not just satellites."
        )
    else:
        lines.append("No high-weight hard disagreements appeared in this run.")
    lines.append("")

    lines.append("## Committee table")
    lines.append("| Symbol | Target Weight | Stance | Confidence |")
    lines.append("|---|---:|---|---:|")
    for r in sorted(rows, key=lambda x: -abs(x["weight"])):
        conf = f"{r['confidence']:.1f}" if isinstance(r["confidence"], float) else "-"
        lines.append(f"| {r['symbol']} | {r['weight']:.1f}% | {r['stance']} | {conf} |")
    lines.append("")

    lines.append("## Why the committee is leaning this way")
    if not theme_counts:
        lines.append("Reason patterns were not strongly clustered in this run.")
    else:
        for theme, count in theme_counts.most_common(5):
            lines.append(f"- `{theme}` appears in {count} ticker rationales.")
    lines.append("")

    lines.append("## Hard-disagree names that matter")
    if not hard:
        lines.append("None in this run.")
    else:
        for r in sorted(hard, key=lambda x: -abs(x["weight"])):
            conf_txt = f"{r['confidence']:.1f}" if isinstance(r["confidence"], float) else "-"
            lines.append(f"- **{r['symbol']} ({r['weight']:.1f}%)** -> `{r['stance']}` ({conf_txt})")
            if r["reasoning"]:
                lines.append(f"  - PM rationale: {r['reasoning']}")
            bears = top_bears.get(r["symbol"], [])
            if bears:
                top = ", ".join([f"{agent} ({conf:.0f})" for agent, conf in bears])
                lines.append(f"  - Most bearish agents: {top}")
    lines.append("")

    lines.append("## Action plan before next rebalance")
    if voice == "bench":
        lines.append("- Respect the bar. Resize before defending the story.")
        lines.append("- Keep sleeve structure, reduce expression where disagreement is strongest.")
        lines.append("- Re-run second-opinion after resizing. Improvement in bucket mix is the validation.")
    else:
        lines.append("- Reduce weights for hard-disagree names.")
        lines.append("- Keep or scale names with strong agreement.")
        lines.append("- Re-run and compare bucket movement.")
    lines.append("")

    lines.append("## Next test")
    lines.append("- Backtest this same ticker set under:")
    lines.append("  - `params_profile=..._baseline`")
    lines.append("  - `params_profile=..._factors_on`")
    lines.append(
        "- Promote only changes that survive both committee disagreement and backtest metrics."
    )
    lines.append("")
    lines.append("---")
    lines.append("Draft generated by `scripts/second_opinion_to_substack_outline.py --final-draft`.")
    return "\n".join(lines) + "\n"


def build_short_note(run_result: dict[str, Any], draft: dict[str, Any], voice: str = "bench") -> str:
    results = run_result.get("results") or {}
    decisions = results.get("decisions") or {}
    meta = results.get("meta") or {}
    sleeve = draft.get("sleeve") or meta.get("sleeve") or "-"
    params_profile = draft.get("params_profile") or meta.get("params_profile") or "-"
    run_id = run_result.get("run_id")
    status = run_result.get("status")

    weights = _weight_map(draft)
    rows: list[dict[str, Any]] = []
    for symbol, decision in decisions.items():
        rows.append(
            {
                "symbol": symbol,
                "stance": _stance(decision),
                "confidence": _safe_float(decision.get("confidence")),
                "weight": float(weights.get(symbol, 0.0)),
                "bucket": _bucket(symbol, _stance(decision), float(weights.get(symbol, 0.0))),
            }
        )
    stance_counts = Counter(r["stance"] for r in rows)
    hard = [r for r in rows if r["bucket"] == "hard_disagree"]
    avg_conf = mean([r["confidence"] for r in rows if isinstance(r["confidence"], float)]) if rows else 0.0

    lines: list[str] = []
    if voice == "bench":
        lines.append("# Bench Note")
        lines.append("")
        lines.append("> Precision. No noise. Just the signal.")
    else:
        lines.append("# Second-opinion note")
    lines.append("")
    lines.append(
        f"Run `{run_id}` (`{status}`) on `{sleeve}` with `{params_profile}`: "
        f"{stance_counts.get('SHORT', 0)} SHORT, {stance_counts.get('BUY', 0)} BUY, "
        f"{stance_counts.get('HOLD', 0)} HOLD."
    )
    lines.append(f"Hard disagreements: {len(hard)}. Average confidence: {avg_conf:.1f}.")
    lines.append("Action: cut expression risk first, then re-run the sleeve and compare bucket deltas.")
    lines.append("")
    return "\n".join(lines) + "\n"


def build_x_thread(run_result: dict[str, Any], draft: dict[str, Any], voice: str = "bench") -> str:
    results = run_result.get("results") or {}
    decisions = results.get("decisions") or {}
    meta = results.get("meta") or {}
    sleeve = draft.get("sleeve") or meta.get("sleeve") or "-"
    params_profile = draft.get("params_profile") or meta.get("params_profile") or "-"
    run_id = run_result.get("run_id")

    weights = _weight_map(draft)
    rows: list[dict[str, Any]] = []
    for symbol, decision in decisions.items():
        stance = _stance(decision)
        conf = _safe_float(decision.get("confidence")) or 0.0
        w = float(weights.get(symbol, 0.0))
        rows.append(
            {
                "symbol": symbol,
                "stance": stance,
                "confidence": conf,
                "weight": w,
                "bucket": _bucket(symbol, stance, w),
            }
        )

    rows_sorted = sorted(rows, key=lambda r: (-abs(r["weight"]), -r["confidence"]))
    hard = [r for r in rows_sorted if r["bucket"] == "hard_disagree"]
    top5 = hard[:5] if hard else rows_sorted[:5]

    lines: list[str] = []
    lines.append("1/ The Bench just ran a full second-opinion pass on the "
                 f"`{sleeve}` sleeve (run {run_id}, profile `{params_profile}`).")
    if voice == "bench":
        lines.append("2/ The benchmark. No substitute. The bar rejected the current expression.")
    else:
        lines.append("2/ Committee output came back with concentrated disagreement.")
    lines.append(
        f"3/ Stance mix: SHORT={sum(1 for r in rows if r['stance']=='SHORT')}, "
        f"BUY={sum(1 for r in rows if r['stance']=='BUY')}, HOLD={sum(1 for r in rows if r['stance']=='HOLD')}."
    )
    lines.append(f"4/ Hard-disagree names: {len(hard)}.")
    if top5:
        lines.append("5/ Biggest names under pressure:")
        for r in top5:
            lines.append(
                f"- {r['symbol']} ({r['weight']:.1f}%) -> {r['stance']} ({r['confidence']:.0f} conf)"
            )
    lines.append("6/ Read: when high-weight names flip hard-disagree, do not defend story with size.")
    lines.append("7/ Action: resize first, preserve sleeve structure, rerun the committee.")
    lines.append("8/ Validation rule: only promote changes that survive both committee + backtest.")
    lines.append("9/ Signal over noise. That is the loop.")
    lines.append("")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate a Substack-ready markdown outline from a second-opinion run."
    )
    parser.add_argument(
        "--run-result",
        required=True,
        type=str,
        help="Path to second_opinion_run_result_<id>.json",
    )
    parser.add_argument(
        "--portfolio-draft",
        required=True,
        type=str,
        help="Path to portfolio draft JSON used for the run.",
    )
    parser.add_argument(
        "--title",
        required=False,
        type=str,
        default=None,
        help="Optional custom essay title.",
    )
    parser.add_argument(
        "--voice",
        required=False,
        type=str,
        default="bench",
        choices=["bench", "neutral"],
        help="Narrative voice style (default: bench).",
    )
    parser.add_argument(
        "--output",
        required=False,
        type=str,
        default=None,
        help="Optional output markdown path. Defaults to second_opinion_runs/substack_outline_run_<id>.md",
    )
    parser.add_argument(
        "--final-draft",
        action="store_true",
        help="Generate a near-publishable prose draft instead of an outline.",
    )
    parser.add_argument(
        "--publish-pack",
        action="store_true",
        help="Generate all outputs at once: outline, final draft, short note, and X thread.",
    )
    args = parser.parse_args()

    run_path = Path(args.run_result)
    draft_path = Path(args.portfolio_draft)
    if not run_path.exists():
        print(f"Run result not found: {run_path}")
        return 1
    if not draft_path.exists():
        print(f"Portfolio draft not found: {draft_path}")
        return 1

    run_result = json.loads(run_path.read_text())
    draft = json.loads(draft_path.read_text())
    run_id = run_result.get("run_id", "unknown")
    out_dir = Path("second_opinion_runs")
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.publish_pack:
        outline = build_outline(run_result, draft, title=args.title, voice=args.voice)
        draft_md = build_final_draft(run_result, draft, title=args.title, voice=args.voice)
        short_note = build_short_note(run_result, draft, voice=args.voice)
        x_thread = build_x_thread(run_result, draft, voice=args.voice)

        outline_path = out_dir / f"substack_outline_run_{run_id}.md"
        draft_path_out = out_dir / f"substack_draft_run_{run_id}.md"
        note_path = out_dir / f"substack_note_run_{run_id}.md"
        thread_path = out_dir / f"x_thread_run_{run_id}.txt"

        outline_path.write_text(outline)
        draft_path_out.write_text(draft_md)
        note_path.write_text(short_note)
        thread_path.write_text(x_thread)

        print(f"Outline written to {outline_path}")
        print(f"Draft written to {draft_path_out}")
        print(f"Short note written to {note_path}")
        print(f"X thread written to {thread_path}")
        return 0

    content = (
        build_final_draft(run_result, draft, title=args.title, voice=args.voice)
        if args.final_draft
        else build_outline(run_result, draft, title=args.title, voice=args.voice)
    )

    default_name = (
        f"substack_draft_run_{run_id}.md" if args.final_draft else f"substack_outline_run_{run_id}.md"
    )
    out_path = Path(args.output) if args.output else out_dir / default_name
    out_path.write_text(content)
    label = "Draft" if args.final_draft else "Outline"
    print(f"{label} written to {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
