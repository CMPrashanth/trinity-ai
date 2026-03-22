"""Check whether main.tex claimed metrics align with measured evaluation output.

Usage:
  python -m scripts.check_report_alignment \
    --results app/data/final_eval_results.json \
    --report ../main.tex \
    --tolerance 0.2
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Dict, Optional, Tuple


def _extract_table_metrics(tex: str) -> Dict[str, float]:
    metrics: Dict[str, float] = {}

    patterns = {
        "hosts_baseline_pct": r"Hosts fully mapped \(avg\.\)\s*&\s*([0-9]+(?:\.[0-9]+)?)\\%",
        "hosts_trinity_pct": r"Hosts fully mapped \(avg\.\)\s*&\s*[0-9]+(?:\.[0-9]+)?\\%\s*&\s*(?:\\textbf\{)?([0-9]+(?:\.[0-9]+)?)\\%",
        "e2e_baseline_pct": r"End-to-end successful runs\s*&\s*([0-9]+(?:\.[0-9]+)?)\\%",
        "e2e_trinity_pct": r"End-to-end successful runs\s*&\s*[0-9]+(?:\.[0-9]+)?\\%[^&]*&\s*(?:\\textbf\{)?([0-9]+(?:\.[0-9]+)?)\\%",
        "logs_baseline_pct": r"Runs with persisted logs\s*&\s*([0-9]+(?:\.[0-9]+)?)\\%",
        "logs_trinity_pct": r"Runs with persisted logs\s*&\s*[0-9]+(?:\.[0-9]+)?\\%[^&]*&\s*(?:\\textbf\{)?([0-9]+(?:\.[0-9]+)?)\\%",
        "vulns_baseline_pct": r"Runs with persisted vulnerabilities\s*&\s*([0-9]+(?:\.[0-9]+)?)\\%",
        "vulns_trinity_pct": r"Runs with persisted vulnerabilities\s*&\s*[0-9]+(?:\.[0-9]+)?\\%[^&]*&\s*(?:\\textbf\{)?([0-9]+(?:\.[0-9]+)?)\\%",
        "retry_baseline_pct": r"First-attempt command success\s*&\s*([0-9]+(?:\.[0-9]+)?)\\%",
        "retry_trinity_pct": r"First-attempt command success\s*&\s*[0-9]+(?:\.[0-9]+)?\\%\s*&\s*(?:\\textbf\{)?([0-9]+(?:\.[0-9]+)?)\\%",
        "recovered_trinity_pct": r"Transient failures recovered\s*&\s*N/A\s*&\s*(?:\\textbf\{)?([0-9]+(?:\.[0-9]+)?)\\%",
    }

    for key, pat in patterns.items():
        m = re.search(pat, tex, flags=re.IGNORECASE)
        if m:
            metrics[key] = float(m.group(1))

    return metrics


def _from_results(payload: Dict) -> Dict[str, float]:
    summary = payload.get("summary", {}) if isinstance(payload, dict) else {}
    baseline = summary.get("baseline", {}) if isinstance(summary, dict) else {}
    trinity = summary.get("trinity", {}) if isinstance(summary, dict) else {}
    b_retry = baseline.get("retry", {}) if isinstance(baseline, dict) else {}
    t_retry = trinity.get("retry", {}) if isinstance(trinity, dict) else {}

    return {
        "hosts_baseline_pct": float(baseline.get("hosts_fully_mapped_avg_pct", 0.0)),
        "hosts_trinity_pct": float(trinity.get("hosts_fully_mapped_avg_pct", 0.0)),
        "e2e_baseline_pct": float(baseline.get("end_to_end_success_pct", 0.0)),
        "e2e_trinity_pct": float(trinity.get("end_to_end_success_pct", 0.0)),
        "logs_baseline_pct": float(baseline.get("runs_with_persisted_logs_pct", 0.0)),
        "logs_trinity_pct": float(trinity.get("runs_with_persisted_logs_pct", 0.0)),
        "vulns_baseline_pct": float(baseline.get("runs_with_persisted_vulns_pct", 0.0)),
        "vulns_trinity_pct": float(trinity.get("runs_with_persisted_vulns_pct", 0.0)),
        "retry_baseline_pct": float(b_retry.get("first_attempt_success_pct", 0.0)),
        "retry_trinity_pct": float(t_retry.get("first_attempt_success_pct", 0.0)),
        "recovered_trinity_pct": float(t_retry.get("transient_recovered_pct", 0.0)),
    }


def _cmp(a: Optional[float], b: Optional[float], tol: float) -> Tuple[bool, float]:
    if a is None or b is None:
        return False, float("inf")
    diff = abs(a - b)
    return diff <= tol, diff


def main() -> int:
    parser = argparse.ArgumentParser(description="Check alignment between main.tex claims and evaluation JSON")
    parser.add_argument("--results", default="app/data/final_eval_results.json")
    parser.add_argument("--report", default="../main.tex")
    parser.add_argument("--tolerance", type=float, default=0.2)
    parser.add_argument("--output", default="app/data/final_eval_alignment.txt")
    args = parser.parse_args()

    results_path = Path(args.results)
    report_path = Path(args.report)

    if not results_path.exists():
        raise FileNotFoundError(f"Results JSON not found: {results_path}")
    if not report_path.exists():
        raise FileNotFoundError(f"Report tex not found: {report_path}")

    payload = json.loads(results_path.read_text(encoding="utf-8"))
    measured = _from_results(payload)
    claims = _extract_table_metrics(report_path.read_text(encoding="utf-8"))

    lines = []
    lines.append("FINAL REPORT ALIGNMENT CHECK")
    lines.append("============================")
    lines.append(f"Tolerance: +/- {args.tolerance:.2f} percentage points")
    lines.append("")

    keys = [
        "hosts_baseline_pct",
        "hosts_trinity_pct",
        "e2e_baseline_pct",
        "e2e_trinity_pct",
        "logs_baseline_pct",
        "logs_trinity_pct",
        "vulns_baseline_pct",
        "vulns_trinity_pct",
        "retry_baseline_pct",
        "retry_trinity_pct",
        "recovered_trinity_pct",
    ]

    passed = 0
    checked = 0

    for key in keys:
        claimed = claims.get(key)
        meas = measured.get(key)
        if claimed is None:
            lines.append(f"[MISSING] {key}: not found in report table")
            continue
        ok, diff = _cmp(claimed, meas, args.tolerance)
        checked += 1
        status = "PASS" if ok else "FAIL"
        if ok:
            passed += 1
        lines.append(
            f"[{status}] {key}: report={claimed:.1f}% measured={meas:.1f}% diff={diff:.1f}"
        )

    lines.append("")
    lines.append(f"Summary: {passed}/{checked} checks passed")
    if checked == 0 or passed < checked:
        lines.append("Action: regenerate LaTeX tables from measured outputs and update main.tex before final submission.")
    else:
        lines.append("Action: report claims align with measured outputs.")

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print("\n".join(lines))
    print(f"\nSaved alignment report: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
