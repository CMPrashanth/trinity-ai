"""Run reproducible Trinity evaluation and export Chapter 9 metrics.

This script executes multiple scan runs in two modes:
- baseline: permissive guard + no graph memory + no self-healing
- trinity: scoped guard + graph memory + self-healing

It persists output in JSON and also writes LaTeX table snippets for report use.

Usage (inside backend container):
  python -m scripts.run_final_evaluation --runs 30 --mode both

Optional:
  python -m scripts.run_final_evaluation --runs 30 --mode both --output app/data/final_eval.json --latex-out app/data/final_eval_tables.tex
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import secrets
from dataclasses import dataclass
from pathlib import Path
from statistics import mean
from typing import Any, Dict, List, Literal, Optional

from app.database import SessionLocal, init_db
from app.models import Log, Scan, ScanStatus, User, UserSettings, Vulnerability
from app.schemas import ScanAdvancedOptions, ScanCreate, ScanProfileEnum
from app.utils.auth import get_password_hash

Mode = Literal["baseline", "trinity"]

GUARD_REJECT_REASONS = {
    "out_of_scope": re.compile(r"out of scope|scope violation|not in authorised subnet|not in authorized subnet", re.IGNORECASE),
    "blocked_t5": re.compile(r"-T5|blocked token: -T5", re.IGNORECASE),
    "destructive": re.compile(r"rm -rf|format|destructive|blocked token", re.IGNORECASE),
}

HOST_SUMMARY_RE = re.compile(r"Scan complete:\s*(?P<hosts>\d+)\s*hosts", re.IGNORECASE)


@dataclass
class Scenario:
    name: str
    description: str
    target: str
    scan_profile: str
    expected_hosts: int
    noisy: bool = False


@dataclass
class RunOutcome:
    mode: Mode
    scenario: Scenario
    scan_db_id: int
    scan_id: str
    status: str
    discovered_hosts: int
    expected_hosts: int
    log_count: int
    vulnerability_count: int
    guard_approved: int
    guard_rejected: int
    guard_rejected_out_of_scope: int
    guard_rejected_t5: int
    guard_rejected_destructive: int
    command_attempts_initial: int
    command_attempts_initial_success: int
    command_attempts_healed: int
    command_attempts_healed_success: int
    circuit_breaker_activated: bool


def load_scenarios(path: Path) -> List[Scenario]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    scenarios: List[Scenario] = []
    for item in payload:
        scenarios.append(
            Scenario(
                name=str(item["name"]),
                description=str(item.get("description", "")),
                target=str(item["target"]),
                scan_profile=str(item.get("scan_profile", "quick")),
                expected_hosts=int(item.get("expected_hosts", 1)),
                noisy=bool(item.get("noisy", False)),
            )
        )
    if not scenarios:
        raise ValueError("No scenarios configured")
    return scenarios


def ensure_eval_user(db) -> User:
    email = "eval@trinity.local"
    user = db.query(User).filter(User.email == email).first()
    if user:
        return user

    user = User(
        name="Trinity Evaluation",
        email=email,
        hashed_password=get_password_hash("eval1234"),
        is_active=True,
        is_admin=True,
    )
    db.add(user)
    db.flush()

    settings = UserSettings(
        user_id=user.id,
        allowed_subnet="10.10.0.0/24",
        blocked_commands=["-T5", "--script=dos", "rm -rf", "format"],
        max_retries=3,
        execution_timeout=45,
        enable_self_healing=True,
        circuit_breaker_enabled=True,
    )
    db.add(settings)
    db.commit()
    db.refresh(user)
    return user


def apply_mode_settings(db, user_id: int, mode: Mode, noisy: bool) -> None:
    settings = db.query(UserSettings).filter(UserSettings.user_id == user_id).first()
    if settings is None:
        settings = UserSettings(user_id=user_id)
        db.add(settings)
        db.flush()

    if mode == "baseline":
        settings.allowed_subnet = "0.0.0.0/0"
        settings.blocked_commands = []
        settings.enable_self_healing = False
        settings.max_retries = 1
        settings.execution_timeout = 30 if not noisy else 20
        settings.circuit_breaker_enabled = False
    else:
        settings.allowed_subnet = "10.10.0.0/24"
        settings.blocked_commands = ["-T5", "--script=dos", "rm -rf", "format"]
        settings.enable_self_healing = True
        settings.max_retries = 3
        settings.execution_timeout = 45 if not noisy else 35
        settings.circuit_breaker_enabled = True

    db.commit()


def classify_guard_reason(text: str) -> Dict[str, int]:
    result = {"out_of_scope": 0, "blocked_t5": 0, "destructive": 0}
    for key, pattern in GUARD_REJECT_REASONS.items():
        if pattern.search(text):
            result[key] = 1
    return result


def _scan_logs(db, scan_db_id: int) -> List[Log]:
    return (
        db.query(Log)
        .filter(Log.scan_id == scan_db_id)
        .order_by(Log.timestamp.asc())
        .all()
    )


def _extract_discovered_hosts(logs: List[Log]) -> int:
    for entry in reversed(logs):
        msg = entry.message or ""
        match = HOST_SUMMARY_RE.search(msg)
        if match:
            return int(match.group("hosts"))
    return 0


def _count_guard_and_command_metrics(logs: List[Log]) -> Dict[str, int | bool]:
    guard_approved = 0
    guard_rejected = 0
    out_of_scope = 0
    t5 = 0
    destructive = 0

    initial_attempts = 0
    initial_success = 0
    healed_attempts = 0
    healed_success = 0

    circuit_open = False

    for entry in logs:
        component = (entry.component or "").strip()
        message = (entry.message or "").strip()
        details = (entry.details or "").strip()
        combo_text = f"{message}\n{details}"

        if "CIRCUIT BREAKER OPEN" in combo_text:
            circuit_open = True

        if component == "Metrics" and message == "guard_decision" and details:
            try:
                payload = json.loads(details)
            except Exception:
                payload = {}
            decision = str(payload.get("decision", "")).lower()
            reason_text = str(payload.get("reason", ""))
            if decision == "approved":
                guard_approved += 1
            elif decision == "rejected":
                guard_rejected += 1
                flags = classify_guard_reason(reason_text)
                out_of_scope += flags["out_of_scope"]
                t5 += flags["blocked_t5"]
                destructive += flags["destructive"]
            continue

        if component == "Guard" and message.startswith("Blocked:"):
            guard_rejected += 1
            flags = classify_guard_reason(combo_text)
            out_of_scope += flags["out_of_scope"]
            t5 += flags["blocked_t5"]
            destructive += flags["destructive"]

        if component == "Metrics" and message == "command_attempt" and details:
            try:
                payload = json.loads(details)
            except Exception:
                payload = {}
            attempt = int(payload.get("attempt", 0) or 0)
            success = bool(payload.get("success", False))
            phase = str(payload.get("phase", "")).lower()
            if phase == "initial" or attempt == 1:
                initial_attempts += 1
                if success:
                    initial_success += 1
            elif phase == "healed" or attempt > 1:
                healed_attempts += 1
                if success:
                    healed_success += 1

    return {
        "guard_approved": guard_approved,
        "guard_rejected": guard_rejected,
        "guard_out_of_scope": out_of_scope,
        "guard_t5": t5,
        "guard_destructive": destructive,
        "initial_attempts": initial_attempts,
        "initial_success": initial_success,
        "healed_attempts": healed_attempts,
        "healed_success": healed_success,
        "circuit_open": circuit_open,
    }


async def run_one(db, user_id: int, mode: Mode, scenario: Scenario) -> RunOutcome:
    try:
        # Lazy import to avoid hard failure when running outside the backend container.
        from app.services.scan_service import ScanService
    except Exception as exc:
        raise RuntimeError(
            "ScanService import failed. Run this command inside the backend container "
            "(docker compose exec backend ...) where dependencies like ollama are installed."
        ) from exc

    apply_mode_settings(db, user_id, mode, scenario.noisy)

    scan_profile = ScanProfileEnum(scenario.scan_profile.lower())
    options = ScanAdvancedOptions(
        enableRAG=True,
        circuitBreaker=(mode == "trinity"),
        graphMemory=(mode == "trinity"),
        autoHeal=(mode == "trinity"),
    )

    scan_payload = ScanCreate(
        target=scenario.target,
        scanProfile=scan_profile,
        advancedOptions=options,
    )

    service = ScanService(db)
    scan = await service.create_scan(scan_payload, user_id)
    await service.start_scan(scan.id)

    db.expire_all()

    persisted_scan = db.query(Scan).filter(Scan.id == scan.id).first()
    logs = _scan_logs(db, scan.id)
    vuln_count = db.query(Vulnerability).filter(Vulnerability.scan_id == scan.id).count()

    discovered_hosts = _extract_discovered_hosts(logs)
    counters = _count_guard_and_command_metrics(logs)

    return RunOutcome(
        mode=mode,
        scenario=scenario,
        scan_db_id=scan.id,
        scan_id=persisted_scan.scan_id,
        status=persisted_scan.status.value,
        discovered_hosts=discovered_hosts,
        expected_hosts=scenario.expected_hosts,
        log_count=len(logs),
        vulnerability_count=vuln_count,
        guard_approved=int(counters["guard_approved"]),
        guard_rejected=int(counters["guard_rejected"]),
        guard_rejected_out_of_scope=int(counters["guard_out_of_scope"]),
        guard_rejected_t5=int(counters["guard_t5"]),
        guard_rejected_destructive=int(counters["guard_destructive"]),
        command_attempts_initial=int(counters["initial_attempts"]),
        command_attempts_initial_success=int(counters["initial_success"]),
        command_attempts_healed=int(counters["healed_attempts"]),
        command_attempts_healed_success=int(counters["healed_success"]),
        circuit_breaker_activated=bool(counters["circuit_open"]),
    )


def _pct(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return (numerator / denominator) * 100.0


def summarize_mode(results: List[RunOutcome]) -> Dict[str, Any]:
    if not results:
        return {}

    total_runs = len(results)
    completed_runs = sum(1 for r in results if r.status == ScanStatus.COMPLETED.value)
    persisted_logs_runs = sum(1 for r in results if r.log_count > 0)
    persisted_vuln_runs = sum(1 for r in results if r.vulnerability_count > 0)

    host_coverages = []
    for r in results:
        if r.expected_hosts > 0:
            host_coverages.append(min(100.0, _pct(r.discovered_hosts, r.expected_hosts)))
        else:
            host_coverages.append(0.0)

    guard_approved = sum(r.guard_approved for r in results)
    guard_rejected = sum(r.guard_rejected for r in results)

    initial_attempts = sum(r.command_attempts_initial for r in results)
    initial_success = sum(r.command_attempts_initial_success for r in results)
    healed_attempts = sum(r.command_attempts_healed for r in results)
    healed_success = sum(r.command_attempts_healed_success for r in results)

    return {
        "runs": total_runs,
        "hosts_fully_mapped_avg_pct": round(mean(host_coverages), 1),
        "end_to_end_success_runs": completed_runs,
        "end_to_end_success_pct": round(_pct(completed_runs, total_runs), 1),
        "runs_with_persisted_logs": persisted_logs_runs,
        "runs_with_persisted_logs_pct": round(_pct(persisted_logs_runs, total_runs), 1),
        "runs_with_persisted_vulns": persisted_vuln_runs,
        "runs_with_persisted_vulns_pct": round(_pct(persisted_vuln_runs, total_runs), 1),
        "guard": {
            "approved": guard_approved,
            "rejected": guard_rejected,
            "rejected_rate_pct": round(_pct(guard_rejected, guard_approved + guard_rejected), 1),
            "out_of_scope": sum(r.guard_rejected_out_of_scope for r in results),
            "blocked_t5": sum(r.guard_rejected_t5 for r in results),
            "destructive": sum(r.guard_rejected_destructive for r in results),
        },
        "retry": {
            "first_attempt_success_pct": round(_pct(initial_success, initial_attempts), 1),
            "initial_attempts": initial_attempts,
            "initial_success": initial_success,
            "transient_failures": max(0, initial_attempts - initial_success),
            "transient_recovered": healed_success,
            "transient_recovered_pct": round(_pct(healed_success, max(0, initial_attempts - initial_success)), 1)
            if initial_attempts - initial_success > 0
            else 0.0,
            "circuit_breaker_activations": sum(1 for r in results if r.circuit_breaker_activated),
        },
    }


def render_latex(summary: Dict[str, Any]) -> str:
    baseline = summary.get("baseline", {})
    trinity = summary.get("trinity", {})

    b_guard = baseline.get("guard", {})
    t_guard = trinity.get("guard", {})
    b_retry = baseline.get("retry", {})
    t_retry = trinity.get("retry", {})

    return f"""% Auto-generated by scripts/run_final_evaluation.py
\\begin{{table}}[h]
\\centering
\\caption{{Final Reconnaissance and Workflow Metrics ({trinity.get('runs', 0)} runs)}}
\\label{{tab:final_recon}}
\\begin{{tabular}}{{lcc}}
\\toprule
\\textbf{{Metric}} & \\textbf{{Stateless Baseline}} & \\textbf{{Trinity (Final)}} \\\\
\\midrule
Hosts fully mapped (avg.) & {baseline.get('hosts_fully_mapped_avg_pct', 0):.1f}\\% & \\textbf{{{trinity.get('hosts_fully_mapped_avg_pct', 0):.1f}\\%}} \\\\
End-to-end successful runs & {baseline.get('end_to_end_success_pct', 0):.1f}\\% ({baseline.get('end_to_end_success_runs', 0)}/{baseline.get('runs', 0)}) & \\textbf{{{trinity.get('end_to_end_success_pct', 0):.1f}\\% ({trinity.get('end_to_end_success_runs', 0)}/{trinity.get('runs', 0)})}} \\\\
Runs with persisted logs & {baseline.get('runs_with_persisted_logs_pct', 0):.1f}\\% ({baseline.get('runs_with_persisted_logs', 0)}/{baseline.get('runs', 0)}) & \\textbf{{{trinity.get('runs_with_persisted_logs_pct', 0):.1f}\\% ({trinity.get('runs_with_persisted_logs', 0)}/{trinity.get('runs', 0)})}} \\\\
Runs with persisted vulnerabilities & {baseline.get('runs_with_persisted_vulns_pct', 0):.1f}\\% ({baseline.get('runs_with_persisted_vulns', 0)}/{baseline.get('runs', 0)}) & \\textbf{{{trinity.get('runs_with_persisted_vulns_pct', 0):.1f}\\% ({trinity.get('runs_with_persisted_vulns', 0)}/{trinity.get('runs', 0)})}} \\\\
\\bottomrule
\\end{{tabular}}
\\end{{table}}

\\begin{{table}}[h]
\\centering
\\caption{{Guard Rejection Breakdown (across {trinity.get('runs', 0)} runs)}}
\\label{{tab:final_guard}}
\\begin{{tabular}}{{lc}}
\\toprule
\\textbf{{Rejection Reason}} & \\textbf{{Count}} \\\\
\\midrule
Out-of-scope IP address & {t_guard.get('out_of_scope', 0)} \\\\
Blocked timing flag (\\texttt{{-T5}}) & {t_guard.get('blocked_t5', 0)} \\\\
Destructive command pattern & {t_guard.get('destructive', 0)} \\\\
\\midrule
\\textbf{{Total rejected / Total generated}} & \\textbf{{{t_guard.get('rejected', 0)} / {t_guard.get('approved', 0) + t_guard.get('rejected', 0)} ({t_guard.get('rejected_rate_pct', 0):.1f}\\%)}} \\\\
\\bottomrule
\\end{{tabular}}
\\end{{table}}

\\begin{{table}}[h]
\\centering
\\caption{{Retry and Recovery Metrics}}
\\label{{tab:final_retry}}
\\begin{{tabular}}{{lcc}}
\\toprule
\\textbf{{Metric}} & \\textbf{{Stateless Baseline}} & \\textbf{{Trinity (Final)}} \\\\
\\midrule
First-attempt command success & {b_retry.get('first_attempt_success_pct', 0):.1f}\\% & \\textbf{{{t_retry.get('first_attempt_success_pct', 0):.1f}\\%}} \\\\
Transient failures recovered & N/A & \\textbf{{{t_retry.get('transient_recovered_pct', 0):.1f}\\% ({t_retry.get('transient_recovered', 0)}/{t_retry.get('transient_failures', 0)})}} \\\\
Circuit-breaker activations & N/A & {t_retry.get('circuit_breaker_activations', 0)}/{trinity.get('runs', 0)} runs \\\\
\\bottomrule
\\end{{tabular}}
\\end{{table}}
"""


def reset_previous_eval_runs(db, user_id: int) -> None:
    scans = db.query(Scan).filter(Scan.user_id == user_id, Scan.scan_id.like("scan-%")).all()
    if not scans:
        return

    scan_ids = [s.id for s in scans]
    db.query(Vulnerability).filter(Vulnerability.scan_id.in_(scan_ids)).delete(synchronize_session=False)
    db.query(Log).filter(Log.scan_id.in_(scan_ids)).delete(synchronize_session=False)
    db.query(Scan).filter(Scan.id.in_(scan_ids)).delete(synchronize_session=False)
    db.commit()


async def run_experiment(
    runs: int,
    mode: Literal["baseline", "trinity", "both"],
    scenarios: List[Scenario],
    reset: bool,
) -> Dict[str, Any]:
    init_db()

    db = SessionLocal()
    try:
        user = ensure_eval_user(db)

        if reset:
            reset_previous_eval_runs(db, user.id)

        modes: List[Mode]
        if mode == "both":
            modes = ["baseline", "trinity"]
        else:
            modes = [mode]

        all_results: Dict[str, List[RunOutcome]] = {"baseline": [], "trinity": []}

        for mode_name in modes:
            for idx in range(runs):
                scenario = scenarios[idx % len(scenarios)]
                result = await run_one(db, user.id, mode_name, scenario)
                all_results[mode_name].append(result)
                print(
                    f"[{mode_name}] run {idx + 1}/{runs} :: scenario={scenario.name} "
                    f"status={result.status} hosts={result.discovered_hosts}/{result.expected_hosts} "
                    f"vulns={result.vulnerability_count}"
                )

        summary = {}
        if all_results["baseline"]:
            summary["baseline"] = summarize_mode(all_results["baseline"])
        if all_results["trinity"]:
            summary["trinity"] = summarize_mode(all_results["trinity"])

        raw_results = {
            "baseline": [r.__dict__ | {"scenario": r.scenario.__dict__} for r in all_results["baseline"]],
            "trinity": [r.__dict__ | {"scenario": r.scenario.__dict__} for r in all_results["trinity"]],
        }

        return {
            "summary": summary,
            "raw_results": raw_results,
            "meta": {
                "runs_per_mode": runs,
                "mode": mode,
                "scenarios": [s.__dict__ for s in scenarios],
            },
        }

    finally:
        db.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Run final Trinity evaluation and export results")
    parser.add_argument("--runs", type=int, default=30, help="Runs per mode")
    parser.add_argument("--mode", choices=["baseline", "trinity", "both"], default="both")
    parser.add_argument("--scenario-file", default="app/data/eval_scenarios.json")
    parser.add_argument("--output", default="app/data/final_eval_results.json")
    parser.add_argument("--latex-out", default="app/data/final_eval_tables.tex")
    parser.add_argument("--reset", action="store_true", help="Clear previous evaluation scans for eval user")

    args = parser.parse_args()

    scenarios = load_scenarios(Path(args.scenario_file))
    result = asyncio.run(
        run_experiment(
            runs=args.runs,
            mode=args.mode,
            scenarios=scenarios,
            reset=args.reset,
        )
    )

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, indent=2), encoding="utf-8")

    latex_path = Path(args.latex_out)
    latex_path.parent.mkdir(parents=True, exist_ok=True)
    latex_path.write_text(render_latex(result.get("summary", {})), encoding="utf-8")

    print(f"Saved JSON results to: {output_path}")
    print(f"Saved LaTeX tables to: {latex_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
