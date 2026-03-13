"""
Agora — Async orchestrator, debate loop, synthesis, and FastAPI SSE server.

Orchestrates the full evaluation pipeline:
  1. Parallel initial evaluations from all 5 agents
  2. Two rounds of structured debate
  3. Final synthesis report
  4. Exposes a Server-Sent Events endpoint for the frontend
"""


from __future__ import annotations

from dotenv import load_dotenv # type: ignore
load_dotenv()

import asyncio
import json
import logging
from dataclasses import asdict
from typing import Awaitable, Callable, Optional

from fastapi import FastAPI  # type: ignore
from fastapi.middleware.cors import CORSMiddleware  # type: ignore
from fastapi.responses import HTMLResponse  # type: ignore
from pydantic import BaseModel  # type: ignore
from sse_starlette.sse import EventSourceResponse  # type: ignore
from pathlib import Path

from agents import (
    PERSONAS,  # type: ignore
    AgentPersona,
    DebateEntry,
    Evaluation,
    PolicyReport,
    SynthesisReport,
    build_debate_prompt,
    build_evaluation_prompt,
    build_synthesis_prompt,
)
from llm import LLMClient, create_llm_client  # type: ignore

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# Single Agent Runners
# ─────────────────────────────────────────────

async def run_single_evaluation(
    persona: AgentPersona,
    policy_text: str,
    llm: LLMClient,
) -> Optional[Evaluation]:
    """Run a single agent evaluation. Returns None on failure (graceful degradation)."""
    try:
        prompt = build_evaluation_prompt(persona, policy_text)
        data = await llm.generate_json(prompt)
        return Evaluation(
            agent_name=persona.name,
            agent_role=persona.role,
            summary=data["summary"],
            strengths=data["strengths"],
            concerns=data["concerns"],
            score=int(data["score"]),
            confidence=int(data["confidence"]),
            key_evidence_quote=data["key_evidence_quote"],
            recommendation=data["recommendation"],
        )
    except Exception as exc:
        logger.error("Agent %s failed during evaluation: %s", persona.name, exc)
        return None


async def run_single_debate(
    persona: AgentPersona,
    policy_text: str,
    all_evaluations: list[dict],
    round_num: int,
    llm: LLMClient,
) -> Optional[DebateEntry]:
    """Run a single agent debate entry. Returns None on failure."""
    try:
        prompt = build_debate_prompt(persona, policy_text, all_evaluations, round_num)
        data = await llm.generate_json(prompt)
        return DebateEntry(
            agent_name=persona.name,
            agent_role=persona.role,
            round_num=round_num,
            addressing=data["addressing"],
            pushback=data["pushback"],
            concession=data["concession"],
            position_shift=data["position_shift"],
            updated_score=int(data["updated_score"]) if data.get("updated_score") is not None else None,
            updated_recommendation=data.get("updated_recommendation"),
        )
    except Exception as exc:
        logger.error("Agent %s failed during debate round %d: %s", persona.name, round_num, exc)
        return None


async def run_synthesis(
    all_evaluations: list[dict],
    all_debate_rounds: list[list[dict]],
    llm: LLMClient,
) -> Optional[SynthesisReport]:
    """Run the synthesis agent. Returns None on failure."""
    try:
        prompt = build_synthesis_prompt(all_evaluations, all_debate_rounds)
        data = await llm.generate_json(prompt)
        return SynthesisReport(
            consensus_level=data["consensus_level"],
            overall_score=float(data["overall_score"]),
            risk_areas=data["risk_areas"],
            top_amendments=data["top_amendments"],
            minority_dissents=data["minority_dissents"],
            narrative_summary=data["narrative_summary"],
        )
    except Exception as exc:
        logger.error("Synthesis agent failed: %s", exc)
        return None


# ─────────────────────────────────────────────
# Pipeline Orchestrator
# ─────────────────────────────────────────────

async def evaluate_policy(
    policy_text: str,
    llm: LLMClient,
    callback: Optional[Callable[[str, dict], Awaitable[None]]] = None,
) -> PolicyReport:
    """Run the full evaluation pipeline. Callback is called with (event_type, data) after each step."""
    report = PolicyReport(policy_text=policy_text)

    # ── Phase 1: Initial Evaluations (parallel) ──
    tasks = [
        run_single_evaluation(persona, policy_text, llm)
        for persona in PERSONAS
    ]

    # Use as_completed pattern so we can stream results progressively
    # type: ignore
    for coro in asyncio.as_completed(tasks):
        result = await coro
        if result is not None:
            report.evaluations.append(result)
            if callback:
                await callback("evaluation", asdict(result))  # type: ignore

    if len(report.evaluations) < 2:
        logger.error("Too few agents completed evaluation (%d). Aborting.", len(report.evaluations))
        if callback:
            await callback("error", {"message": "Too few agents completed evaluation"})  # type: ignore
        return report

    eval_dicts = [asdict(e) for e in report.evaluations]

    # ── Phase 2: Debate Loop (2 rounds) ──
    all_debate_dicts: list[list[dict]] = []

    # Build a set of names that completed evaluation — used to gate debate participation.
    # Assert every name maps back to a known persona so name drift is caught immediately.
    evaluated_names: set[str] = {e.agent_name for e in report.evaluations}
    known_names: set[str] = {p.name for p in PERSONAS}
    unknown = evaluated_names - known_names
    if unknown:
        raise ValueError(f"Evaluated agent names not found in PERSONAS: {unknown}")

    for round_num in range(1, 3):
        if callback:
            await callback("debate_round_start", {"round": round_num})  # type: ignore

        debate_tasks = [
            run_single_debate(persona, policy_text, eval_dicts, round_num, llm)
            for persona in PERSONAS
            if persona.name in evaluated_names
        ]

        round_entries: list[DebateEntry] = []
        # type: ignore
        for coro in asyncio.as_completed(debate_tasks):
            result = await coro
            if result is not None:
                round_entries.append(result)
                if callback:
                    await callback("debate", asdict(result))  # type: ignore

        report.debate_rounds.append(round_entries)
        round_dicts = [asdict(e) for e in round_entries]
        all_debate_dicts.append(round_dicts)

        # Update eval scores and recommendations for agents whose positions shifted
        for entry in round_entries:
            for ed in eval_dicts:
                if ed["agent_name"] == entry.agent_name:
                    if entry.updated_score is not None:
                        ed["score"] = entry.updated_score
                    if entry.updated_recommendation is not None:
                        ed["recommendation"] = entry.updated_recommendation

    # ── Phase 3: Synthesis ──
    if callback:
        await callback("synthesis_start", {})  # type: ignore

    synthesis = await run_synthesis(eval_dicts, all_debate_dicts, llm)  # type: ignore
    if synthesis:
        report.synthesis = synthesis
        if callback:
            await callback("synthesis", asdict(synthesis))  # type: ignore

    if callback:
        await callback("complete", {})  # type: ignore

    return report


# ─────────────────────────────────────────────
# FastAPI Server with SSE
# ─────────────────────────────────────────────

app = FastAPI(title="Agora Policy Evaluator")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Singleton LLM client — shared across all requests so the semaphore and
# rate-limit tracker are global, not per-request.
_llm = create_llm_client()


class EvaluateRequest(BaseModel):
    policy_text: str

@app.get("/")
async def serve_frontend():
    """Serve the frontend index.html."""
    html_content = Path("index.html").read_text(encoding="utf-8")
    return HTMLResponse(html_content)


@app.get("/api/evaluate")
async def api_evaluate(policy_text: str):
    """Evaluate a policy and stream results via Server-Sent Events."""

    async def event_generator():
        queue: asyncio.Queue = asyncio.Queue()

        async def sse_callback(event_type: str, data: dict):
            await queue.put({"event": event_type, "data": json.dumps(data)})

        async def run_pipeline():
            try:
                await evaluate_policy(policy_text, _llm, callback=sse_callback)  # type: ignore
            except Exception as exc:
                await queue.put({"event": "error", "data": json.dumps({"message": str(exc)})})
            finally:
                await queue.put(None)  # Sentinel to stop the generator

        # Start pipeline in background
        asyncio.create_task(run_pipeline())

        # Yield events as they arrive
        while True:
            item = await queue.get()
            if item is None:
                break
            yield item

    return EventSourceResponse(event_generator())
