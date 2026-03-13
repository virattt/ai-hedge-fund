"""
scripts/dexter_second_opinion_client.py — Dexter helper for second-opinion runs.

This script is designed to be called from Dexter (or manually) to:
  1. Read a PortfolioDraft JSON file (one sleeve),
  2. Submit a second-opinion job to the local AI Hedge Fund API, and
  3. Poll until completion and optionally print a disagreement report.

Usage (from ai-hedge-fund repo root):

    python scripts/dexter_second_opinion_client.py \
      --draft path/to/portfolio_draft.json \
      --run-report

Dexter can either:
  - shell out to this script, or
  - copy its logic into a native Python client.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any, Dict

import requests


def fetch_flow_graph(base_url: str, flow_id: int) -> tuple[list[dict], list[dict]]:
    """Fetch nodes/edges from a saved flow via API."""
    base = base_url.rstrip("/")
    candidate_urls = [
        f"{base}/api/v1/flows/{flow_id}",
        f"{base}/flows/{flow_id}",
    ]
    resp = None
    last_error_url = None
    for url in candidate_urls:
        r = requests.get(url, timeout=30)
        if r.status_code == 404:
            last_error_url = url
            continue
        resp = r
        break

    if resp is None:
        # Preserve the previous debug behavior when no route matched.
        if last_error_url:
            print(f"HTTP 404 from {last_error_url}")
        raise requests.HTTPError("Flow endpoint not found on backend (tried /api/v1/flows and /flows)")

    if resp.status_code >= 400:
        print(f"HTTP {resp.status_code} from {resp.url}")
        try:
            print(resp.text)
        except Exception:
            pass
        resp.raise_for_status()

    flow = resp.json()
    nodes = flow.get("nodes") or []
    edges = flow.get("edges") or []
    return nodes, edges


def validate_graph_or_raise(graph_nodes: list[dict], graph_edges: list[dict]) -> None:
    """Hard validation so we fail early instead of hanging with empty decisions."""
    if not graph_nodes:
        raise ValueError("graph_nodes is empty. Provide a flow graph or pass --flow-id.")
    if not graph_edges:
        raise ValueError("graph_edges is empty. Provide a flow graph or pass --flow-id.")

    for idx, node in enumerate(graph_nodes):
        if not isinstance(node, dict) or not node.get("id"):
            raise ValueError(f"graph_nodes[{idx}] is missing required field 'id'.")

    for idx, edge in enumerate(graph_edges):
        if not isinstance(edge, dict):
            raise ValueError(f"graph_edges[{idx}] must be an object.")
        if not edge.get("source") or not edge.get("target"):
            raise ValueError(f"graph_edges[{idx}] must include 'source' and 'target'.")

    node_ids = {str(n.get("id")) for n in graph_nodes}
    for idx, edge in enumerate(graph_edges):
        src = str(edge.get("source"))
        tgt = str(edge.get("target"))
        if src not in node_ids:
            raise ValueError(f"graph_edges[{idx}].source references unknown node '{src}'.")
        if tgt not in node_ids:
            raise ValueError(f"graph_edges[{idx}].target references unknown node '{tgt}'.")


def _normalize_edge_endpoint(node_ids: set[str], endpoint: str) -> str:
    """
    Normalize flow edge endpoints that may carry legacy random suffixes.

    Example:
      stock-analyzer-node_ibswfz -> stock-analyzer-node
    """
    if endpoint in node_ids:
        return endpoint
    if "_" in endpoint:
        candidate = endpoint.rsplit("_", 1)[0]
        if candidate in node_ids:
            return candidate
    return endpoint


def normalize_graph_edges(graph_nodes: list[dict], graph_edges: list[dict]) -> list[dict]:
    """Return edges with source/target normalized against known node IDs."""
    node_ids = {str(n.get("id")) for n in graph_nodes if isinstance(n, dict) and n.get("id")}
    normalized: list[dict] = []
    for edge in graph_edges:
        if not isinstance(edge, dict):
            normalized.append(edge)
            continue
        src = str(edge.get("source")) if edge.get("source") is not None else ""
        tgt = str(edge.get("target")) if edge.get("target") is not None else ""
        normalized.append(
            {
                **edge,
                "source": _normalize_edge_endpoint(node_ids, src),
                "target": _normalize_edge_endpoint(node_ids, tgt),
            }
        )
    return normalized


def submit_run(base_url: str, draft: Dict[str, Any], params_profile: str | None = None) -> int:
    """POST the draft as a HedgeFundRequest-compatible body and return run_id."""
    url = f"{base_url.rstrip('/')}/api/v1/second-opinion/runs"

    # Minimal mapping: we assume the draft contains tickers and a prebuilt graph
    # Normalize model provider to match the backend enum expectations.
    raw_provider = draft.get("model_provider", "OpenAI")
    if isinstance(raw_provider, str) and raw_provider.lower() == "openai":
        model_provider = "OpenAI"
    else:
        model_provider = raw_provider

    body: Dict[str, Any] = {
        "tickers": [a["symbol"] for a in draft.get("assets", [])],
        "sleeve": draft.get("sleeve"),
        "params_profile": params_profile or draft.get("params_profile"),
        "graph_nodes": draft.get("graph_nodes", []),
        "graph_edges": draft.get("graph_edges", []),
        "margin_requirement": draft.get("margin_requirement", 0.0),
        "portfolio_positions": draft.get("portfolio_positions", []),
        "model_name": draft.get("model_name", "gpt-4.1"),
        "model_provider": model_provider,
        "api_keys": draft.get("api_keys"),
    }

    resp = requests.post(url, json=body, timeout=30)
    if resp.status_code >= 400:
        # Surface validation / server errors to the caller for easier debugging.
        print(f"HTTP {resp.status_code} from {url}")
        try:
            print(resp.text)
        except Exception:
            pass
        resp.raise_for_status()
    data = resp.json()
    return int(data["run_id"])


def _fmt_elapsed(seconds: float) -> str:
    total = int(max(0, seconds))
    m, s = divmod(total, 60)
    h, m = divmod(m, 60)
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def poll_status(
    base_url: str,
    run_id: int,
    poll_interval: float,
    timeout_s: float,
    show_progress: bool = True,
) -> Dict[str, Any]:
    """Poll /runs/{run_id} until terminal status or timeout."""
    url = f"{base_url.rstrip('/')}/api/v1/second-opinion/runs/{run_id}"
    t0 = time.time()
    poll_count = 0
    last_status = None
    while True:
        poll_count += 1
        resp = requests.get(url, timeout=15)
        if resp.status_code == 404:
            raise RuntimeError(f"Run {run_id} not found")
        resp.raise_for_status()
        data = resp.json()
        status = data.get("status")
        elapsed = time.time() - t0

        if show_progress:
            changed = status != last_status
            marker = "*" if changed else "-"
            print(
                f"  {marker} [{_fmt_elapsed(elapsed)}] poll={poll_count} status={status}",
                flush=True,
            )
        last_status = status

        if status in ("COMPLETE", "ERROR", "FAILED", "CANCELLED"):
            return data
        if elapsed > timeout_s:
            raise TimeoutError(f"Timed out waiting for run {run_id} (last status={status})")
        time.sleep(poll_interval)


def fetch_result(base_url: str, run_id: int) -> Dict[str, Any]:
    """GET the final result payload once status is COMPLETE/ERROR."""
    url = f"{base_url.rstrip('/')}/api/v1/second-opinion/runs/{run_id}/result"
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    return resp.json()


def main() -> int:
    parser = argparse.ArgumentParser(description="Dexter helper: submit a second-opinion run and optionally report.")
    parser.add_argument(
        "--draft",
        type=str,
        required=True,
        help="Path to PortfolioDraft JSON (one sleeve).",
    )
    parser.add_argument(
        "--base-url",
        type=str,
        default="http://localhost:8000",
        help="Base URL for AI Hedge Fund backend (default http://localhost:8000).",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=".",
        help="Directory to write run_result_<run_id>.json (default current dir).",
    )
    parser.add_argument(
        "--poll-interval",
        type=float,
        default=2.0,
        help="Seconds between status polls.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=900.0,
        help="Max seconds to wait for a run (default 900s = 15min).",
    )
    parser.add_argument(
        "--hide-progress",
        action="store_true",
        help="Hide per-poll progress lines while waiting for completion.",
    )
    parser.add_argument(
        "--run-report",
        action="store_true",
        help="After fetching result, run the terminal disagreement report.",
    )
    parser.add_argument(
        "--params-profile",
        type=str,
        default=None,
        help="Optional params profile hint (e.g. tastytrade_baseline, tastytrade_factors_on).",
    )
    parser.add_argument(
        "--flow-id",
        type=int,
        default=None,
        help="Optional saved flow ID to auto-populate graph_nodes/graph_edges from /api/v1/flows/{flow_id}.",
    )

    args = parser.parse_args()

    draft_path = Path(args.draft)
    if not draft_path.exists():
        print(f"Draft file not found: {draft_path}")
        return 1
    draft = json.loads(draft_path.read_text())

    graph_nodes = draft.get("graph_nodes") or []
    graph_edges = draft.get("graph_edges") or []

    # If flow ID is provided, use saved flow graph as the source of truth.
    if args.flow_id is not None:
        print(f"Loading graph from flow_id={args.flow_id} ...")
        graph_nodes, graph_edges = fetch_flow_graph(args.base_url, args.flow_id)
        graph_edges = normalize_graph_edges(graph_nodes, graph_edges)
        draft["graph_nodes"] = graph_nodes
        draft["graph_edges"] = graph_edges
        print(f"  loaded graph: {len(graph_nodes)} nodes, {len(graph_edges)} edges")

    # Hard fail if graph is invalid.
    validate_graph_or_raise(graph_nodes, graph_edges)

    print(f"Submitting second-opinion run to {args.base_url} for {draft_path}...")
    run_id = submit_run(args.base_url, draft, params_profile=args.params_profile)
    print(f"  → run_id={run_id}")

    print("Polling status...")
    status_data = poll_status(
        args.base_url,
        run_id,
        args.poll_interval,
        args.timeout,
        show_progress=not args.hide_progress,
    )
    print(f"  final status: {status_data.get('status')}")
    if status_data.get("error_message"):
        print(f"  error_message: {status_data['error_message']}")

    print("Fetching result...")
    result = fetch_result(args.base_url, run_id)
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    result_path = out_dir / f"second_opinion_run_result_{run_id}.json"
    result_path.write_text(json.dumps(result, indent=2))
    print(f"  result written to {result_path}")

    if args.run_report:
        try:
            from autoresearch.second_opinion_report import main as report_main  # type: ignore

            # Construct a minimal PortfolioDraft-like dict the report expects
            assets = draft.get("assets", [])
            draft_for_report = {
                "sleeve": draft.get("sleeve"),
                "params_profile": args.params_profile or draft.get("params_profile"),
                "assets": assets,
            }
            tmp_draft = out_dir / f"second_opinion_portfolio_draft_{run_id}.json"
            tmp_draft.write_text(json.dumps(draft_for_report, indent=2))

            print("\n=== Second-opinion comparison ===")
            # The report CLI expects file paths via argv; emulate that
            import sys

            argv_backup = sys.argv
            try:
                sys.argv = [
                    "second_opinion_report",
                    "--portfolio-draft",
                    str(tmp_draft),
                    "--run-result",
                    str(result_path),
                ]
                report_main()
            finally:
                sys.argv = argv_backup
        except Exception as e:
            print(f"(report generation failed: {e})")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

