"""
Agora — CLI entrypoint for policy evaluation.

Usage:
    python run_eval.py --policy "path/to/policy.txt"

Prints a formatted terminal summary and saves a JSON report to report.json.
"""

from __future__ import annotations

from dotenv import load_dotenv # type: ignore
load_dotenv()

import argparse
import asyncio
import json
import sys
from pathlib import Path


from agents import PolicyReport  # type: ignore
from llm import create_llm_client  # type: ignore
from runner import evaluate_policy  # type: ignore


# ─────────────────────────────────────────────
# Terminal Formatting
# ─────────────────────────────────────────────

class Colors:
    BOLD = "\033[1m"
    DIM = "\033[2m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    CYAN = "\033[96m"
    MAGENTA = "\033[95m"
    BLUE = "\033[94m"
    RESET = "\033[0m"


def score_color(score: int) -> str:
    if score >= 7:
        return Colors.GREEN
    elif score >= 4:
        return Colors.YELLOW
    else:
        return Colors.RED


def rec_color(rec: str) -> str:
    if rec == "approve":
        return Colors.GREEN
    elif rec == "approve_with_changes":
        return Colors.YELLOW
    else:
        return Colors.RED


def print_header(text: str):
    width = 60
    print(f"\n{Colors.CYAN}{'═' * width}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.CYAN}  {text}{Colors.RESET}")
    print(f"{Colors.CYAN}{'═' * width}{Colors.RESET}")


def print_subheader(text: str):
    print(f"\n{Colors.MAGENTA}── {text} ──{Colors.RESET}")


def print_report(report: PolicyReport):
    """Print a formatted terminal summary of the evaluation."""
    print_header("AGORA POLICY EVALUATION REPORT")

    # ── Agent Evaluations ──
    print_subheader("AGENT EVALUATIONS")
    for e in report.evaluations:
        sc = score_color(e.score)
        rc = rec_color(e.recommendation)
        print(f"\n  {Colors.BOLD}{e.agent_name}{Colors.RESET} ({Colors.DIM}{e.agent_role}{Colors.RESET})")
        print(f"  Score: {sc}{e.score}/10{Colors.RESET}  |  Confidence: {e.confidence}/10  |  Rec: {rc}{e.recommendation}{Colors.RESET}")
        print(f"  {Colors.DIM}{e.summary}{Colors.RESET}")
        print(f"  {Colors.DIM}Strengths:{Colors.RESET}")
        for s in e.strengths:
            print(f"    {Colors.GREEN}+{Colors.RESET} {s}")
        print(f"  {Colors.DIM}Concerns:{Colors.RESET}")
        for c in e.concerns:
            print(f"    {Colors.RED}-{Colors.RESET} {c}")
        print(f'  {Colors.DIM}Key quote: "{e.key_evidence_quote}"{Colors.RESET}')

    # ── Debate Rounds ──
    for round_idx, round_entries in enumerate(report.debate_rounds, 1):
        print_subheader(f"DEBATE ROUND {round_idx}")
        for d in round_entries:
            shift_color = Colors.GREEN if d.position_shift == "unchanged" else Colors.YELLOW
            print(f"\n  {Colors.BOLD}{d.agent_name}{Colors.RESET} → addressing {', '.join(d.addressing)}")
            print(f"  Position: {shift_color}{d.position_shift}{Colors.RESET}", end="")
            if d.updated_score is not None:
                print(f"  |  New score: {score_color(d.updated_score)}{d.updated_score}/10{Colors.RESET}")
            else:
                print()
            print(f"  {Colors.DIM}Pushback: {d.pushback}{Colors.RESET}")
            if d.concession and d.concession.lower() != "none":
                print(f"  {Colors.BLUE}Concession: {d.concession}{Colors.RESET}")

    # ── Synthesis ──
    if report.synthesis:
        s = report.synthesis
        print_header("SYNTHESIS")

        consensus_colors = {
            "strong": Colors.GREEN,
            "moderate": Colors.YELLOW,
            "contested": Colors.RED,
            "deadlocked": Colors.RED,
        }
        cc = consensus_colors.get(s.consensus_level, Colors.RESET)

        print(f"\n  Consensus: {cc}{s.consensus_level.upper()}{Colors.RESET}")
        print(f"  Overall Score: {score_color(int(s.overall_score))}{s.overall_score}/10{Colors.RESET}")
        print(f"\n  {Colors.DIM}{s.narrative_summary}{Colors.RESET}")

        print(f"\n  {Colors.BOLD}Risk Areas:{Colors.RESET}")
        for r in s.risk_areas:
            sev_color = Colors.RED if r["severity"] == "high" else Colors.YELLOW if r["severity"] == "medium" else Colors.GREEN
            print(f"    {sev_color}[{r['severity'].upper()}]{Colors.RESET} {r['area']}")

        print(f"\n  {Colors.BOLD}Top Amendments:{Colors.RESET}")
        for i, a in enumerate(s.top_amendments, 1):
            print(f"    {i}. {a}")

        if s.minority_dissents:
            print(f"\n  {Colors.BOLD}Minority Dissents:{Colors.RESET}")
            for d in s.minority_dissents:
                print(f"    {Colors.YELLOW}⚠{Colors.RESET} {d}")

    print(f"\n{Colors.CYAN}{'═' * 60}{Colors.RESET}\n")


# ─────────────────────────────────────────────
# CLI Callback (progressive display)
# ─────────────────────────────────────────────

async def cli_callback(event_type: str, data: dict):
    """Show progress in the terminal as agents complete."""
    if event_type == "evaluation":
        sc = score_color(data["score"])
        rc = rec_color(data["recommendation"])
        print(
            f"  {Colors.GREEN}✓{Colors.RESET} {data['agent_name']} ({data['agent_role']}) "
            f"— Score: {sc}{data['score']}/10{Colors.RESET} "
            f"— Rec: {rc}{data['recommendation']}{Colors.RESET}"
        )
    elif event_type == "debate_round_start":
        print(f"\n{Colors.MAGENTA}  ⟳ Starting debate round {data['round']}...{Colors.RESET}")
    elif event_type == "debate":
        shift = data["position_shift"]
        shift_icon = "→" if shift == "unchanged" else "↻"
        print(
            f"  {Colors.BLUE}{shift_icon}{Colors.RESET} {data['agent_name']} "
            f"— {shift}"
            + (f" (new score: {data['updated_score']})" if data.get("updated_score") is not None else "")
        )
    elif event_type == "synthesis_start":
        print(f"\n{Colors.CYAN}  ◉ Generating synthesis...{Colors.RESET}")
    elif event_type == "complete":
        print(f"\n{Colors.GREEN}  ✓ Evaluation complete!{Colors.RESET}")


# ─────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────

async def main():
    parser = argparse.ArgumentParser(
        description="Agora — AI-Powered Policy Evaluation System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Example: python run_eval.py --policy sample_policy.txt",
    )
    parser.add_argument(
        "--policy",
        type=str,
        required=True,
        help="Path to the policy text file to evaluate",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="report.json",
        help="Path to save the JSON report (default: report.json)",
    )
    args = parser.parse_args()

    policy_path = Path(args.policy)
    if not policy_path.exists():
        print(f"{Colors.RED}Error: Policy file not found: {policy_path}{Colors.RESET}")
        sys.exit(1)

    policy_text = policy_path.read_text(encoding="utf-8")

    print_header("AGORA POLICY EVALUATOR")
    print(f"\n  Policy: {Colors.BOLD}{policy_path.name}{Colors.RESET}")
    print(f"  Length: {len(policy_text)} characters")
    print(f"\n{Colors.DIM}  Running evaluation with 5 AI agents...{Colors.RESET}\n")

    llm = create_llm_client()
    report = await evaluate_policy(policy_text, llm, callback=cli_callback)

    # Print full report
    print_report(report)

    # Save JSON
    output_path = Path(args.output)
    output_path.write_text(report.to_json(), encoding="utf-8")
    print(f"  {Colors.GREEN}Report saved to {output_path}{Colors.RESET}\n")


if __name__ == "__main__":
    asyncio.run(main())
