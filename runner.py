"""
Agora — Async orchestrator, debate loop, synthesis, and FastAPI SSE server.

Now includes Tavily research retrieval.
"""

from __future__ import annotations

from dotenv import load_dotenv  # type: ignore
load_dotenv()

import asyncio
import json
import logging
from dataclasses import asdict
from typing import Awaitable, Callable, Optional
from pathlib import Path

from fastapi import FastAPI  # type: ignore
from fastapi.middleware.cors import CORSMiddleware  # type: ignore
from fastapi.responses import HTMLResponse  # type: ignore
from pydantic import BaseModel  # type: ignore
from sse_starlette.sse import EventSourceResponse  # type: ignore

from agents import (  # type: ignore
    PERSONAS,
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
from research import search_policy_evidence  # type: ignore

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# Agent Execution
# ─────────────────────────────────────────────

async def run_single_evaluation(
    persona: AgentPersona,
    policy_text: str,
    llm: LLMClient,
) -> Optional[Evaluation]:

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

    # ── Tavily Research Step ──

    evidence = ""

    try:
        evidence = await asyncio.to_thread(search_policy_evidence, policy_text)  # type: ignore
    except Exception as exc:
        logger.warning("Policy research failed: %s", exc)

    policy_with_evidence = f"""
{policy_text}

REAL WORLD POLICY EVIDENCE
─────────────────────────────────
The following examples come from real-world policies or research.
Use them as supporting evidence when relevant.

{evidence}
"""

    report = PolicyReport(policy_text=policy_with_evidence)

    # ── Phase 1: Initial Evaluations (parallel) ──

    tasks = [
        run_single_evaluation(persona, policy_with_evidence, llm)
        for persona in PERSONAS
    ]

    for coro in asyncio.as_completed(tasks):  # type: ignore
        result = await coro

        if result is not None:
            report.evaluations.append(result)

            if callback:
                await callback("evaluation", asdict(result))  # type: ignore

    if len(report.evaluations) < 2:
        logger.error("Too few agents completed evaluation")

        if callback:
            await callback("error", {"message": "Too few agents completed evaluation"})  # type: ignore

        return report

    eval_dicts = [asdict(e) for e in report.evaluations]

    # ── Phase 2: Debate Loop ──

    all_debate_dicts: list[list[dict]] = []

    evaluated_names: set[str] = {e.agent_name for e in report.evaluations}

    for round_num in range(1, 3):

        if callback:
            await callback("debate_round_start", {"round": round_num})  # type: ignore

        debate_tasks = [
            run_single_debate(persona, policy_with_evidence, eval_dicts, round_num, llm)
            for persona in PERSONAS
            if persona.name in evaluated_names
        ]

        round_entries: list[DebateEntry] = []

        for coro in asyncio.as_completed(debate_tasks):  # type: ignore
            result = await coro

            if result is not None:
                round_entries.append(result)

                if callback:
                    await callback("debate", asdict(result))  # type: ignore

        report.debate_rounds.append(round_entries)

        round_dicts = [asdict(e) for e in round_entries]
        all_debate_dicts.append(round_dicts)

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
# FastAPI Server
# ─────────────────────────────────────────────

app = FastAPI(title="Agora Policy Evaluator")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_llm = create_llm_client()  # type: ignore


class EvaluateRequest(BaseModel):
    policy_text: str


@app.get("/")
async def serve_frontend():
    html_content = Path("index.html").read_text(encoding="utf-8")
    return HTMLResponse(html_content)


@app.get("/api/evaluate")
async def api_evaluate(policy_text: str):

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
                await queue.put(None)

        asyncio.create_task(run_pipeline())

        while True:

            item = await queue.get()

            if item is None:
                break

            yield item

    return EventSourceResponse(event_generator())  # type: ignore