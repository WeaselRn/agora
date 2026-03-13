"""
Agora — Agent persona definitions, prompt builders, and dataclasses.

Defines the 5 stakeholder personas and all structured data types used
throughout the policy evaluation pipeline.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from typing import List, Optional


# ─────────────────────────────────────────────
# Data Classes
# ─────────────────────────────────────────────

@dataclass
class AgentPersona:
    name: str
    role: str
    analytical_lens: str
    priorities: List[str]
    skeptical_of: str


@dataclass
class Evaluation:
    agent_name: str
    agent_role: str
    summary: str
    strengths: List[str]
    concerns: List[str]
    score: int
    confidence: int
    key_evidence_quote: str
    recommendation: str  # approve | approve_with_changes | reject


@dataclass
class DebateEntry:
    agent_name: str
    agent_role: str
    round_num: int
    addressing: List[str]
    pushback: str
    concession: str
    position_shift: str  # unchanged | softened | hardened | revised
    updated_score: Optional[int] = None


@dataclass
class SynthesisReport:
    consensus_level: str  # strong | moderate | contested | deadlocked
    overall_score: float
    risk_areas: List[dict]  # [{"area": str, "severity": "high"|"medium"|"low"}]
    top_amendments: List[str]
    minority_dissents: List[str]
    narrative_summary: str


@dataclass
class PolicyReport:
    policy_text: str
    evaluations: List[Evaluation] = field(default_factory=list)
    debate_rounds: List[List[DebateEntry]] = field(default_factory=list)
    synthesis: Optional[SynthesisReport] = None

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)


# ─────────────────────────────────────────────
# Hardcoded Personas
# ─────────────────────────────────────────────

PERSONAS: List[AgentPersona] = [
    AgentPersona(
        name="Dr. Arvind Mehta",
        role="Economist",
        analytical_lens="Cost-benefit analysis, fiscal sustainability, market distortion effects, and macroeconomic impact",
        priorities=[
            "Budget efficiency and ROI",
            "Long-term fiscal sustainability",
            "Impact on economic growth and employment",
            "Avoiding market distortions and perverse incentives",
        ],
        skeptical_of="Policies with high upfront costs, vague funding mechanisms, or those that create dependency traps rather than self-sustaining systems",
    ),
    AgentPersona(
        name="Justice Priya Sundaram",
        role="Legal Expert",
        analytical_lens="Constitutional validity, regulatory compliance, enforcement mechanisms, and precedent analysis",
        priorities=[
            "Legal enforceability and clarity of language",
            "Constitutional and human rights alignment",
            "Jurisdictional authority and inter-agency coordination",
            "Liability allocation and dispute resolution pathways",
        ],
        skeptical_of="Policies that grant broad discretionary powers without oversight, create ambiguous mandates, or conflict with existing legal frameworks",
    ),
    AgentPersona(
        name="Prof. Lena Okonkwo",
        role="Ethicist",
        analytical_lens="Equity, justice, informed consent, vulnerability assessment, and long-term societal impact",
        priorities=[
            "Fairness across socioeconomic and demographic groups",
            "Protection of vulnerable populations",
            "Transparency and informed consent in implementation",
            "Avoiding surveillance overreach and privacy erosion",
        ],
        skeptical_of="Techno-solutionist approaches that trade civil liberties for efficiency, or policies that disproportionately burden marginalized communities",
    ),
    AgentPersona(
        name="Director Raj Kulkarni",
        role="Implementation Officer",
        analytical_lens="Operational feasibility, institutional capacity, resource allocation, and timeline realism",
        priorities=[
            "Practical deployability with existing infrastructure",
            "Inter-departmental coordination requirements",
            "Workforce readiness and training needs",
            "Phased rollout strategy and contingency planning",
        ],
        skeptical_of="Policies that assume perfect institutional coordination, ignore ground-level capacity constraints, or set unrealistic timelines without fallback plans",
    ),
    AgentPersona(
        name="Amara Singh",
        role="Citizen Representative",
        analytical_lens="Lived experience impact, public accessibility, community trust, and practical daily-life consequences",
        priorities=[
            "Direct impact on daily life of ordinary citizens",
            "Accessibility for low-income and non-tech-savvy populations",
            "Community trust and transparency of processes",
            "Avoiding creation of new bureaucratic hurdles",
        ],
        skeptical_of="Top-down policies designed without community input, those requiring digital literacy or infrastructure that marginalized communities lack, or policies that look good on paper but fail on the ground",
    ),
]


# ─────────────────────────────────────────────
# Prompt Builders
# ─────────────────────────────────────────────

def build_evaluation_prompt(persona: AgentPersona, policy_text: str) -> str:
    return f"""You are {persona.name}, a {persona.role}.

YOUR ANALYTICAL LENS: {persona.analytical_lens}

YOUR PRIORITIES (in order of importance):
{chr(10).join(f"  {i+1}. {p}" for i, p in enumerate(persona.priorities))}

YOU ARE ESPECIALLY SKEPTICAL OF: {persona.skeptical_of}

─────────────────────────────────
POLICY TEXT TO EVALUATE:
─────────────────────────────────
{policy_text}
─────────────────────────────────

TASK: Provide a rigorous, opinionated evaluation of this policy from your professional perspective. DO NOT be diplomatically vague — be specific about what works and what doesn't. Name concrete failure modes. If the policy is weak, say so plainly.

You MUST respond with ONLY a valid JSON object (no markdown, no explanation outside the JSON) matching this exact schema:

{{
  "summary": "A 2-3 sentence executive summary of your assessment — be direct",
  "strengths": ["Specific strength 1 with evidence", "Specific strength 2 with evidence"],
  "concerns": ["Specific concern 1 with concrete risk", "Specific concern 2 with concrete risk"],
  "score": <integer 1-10 where 1=fundamentally flawed and 10=excellent>,
  "confidence": <integer 1-10 reflecting how confident you are in your assessment>,
  "key_evidence_quote": "A direct quote or paraphrase from the policy text that most informed your evaluation",
  "recommendation": "<exactly one of: approve | approve_with_changes | reject>"
}}

Be sharp. Be specific. Name names, cite numbers, identify gaps. Generic praise or vague concerns are unacceptable."""


def build_debate_prompt(
    persona: AgentPersona,
    policy_text: str,
    all_evaluations: List[dict],
    round_num: int,
) -> str:
    other_evals = [e for e in all_evaluations if e["agent_name"] != persona.name]
    evals_text = "\n\n".join(
        f"── {e['agent_name']} ({e['agent_role']}) — Score: {e['score']}/10, Rec: {e['recommendation']} ──\n"
        f"Summary: {e['summary']}\n"
        f"Strengths: {json.dumps(e['strengths'])}\n"
        f"Concerns: {json.dumps(e['concerns'])}"
        for e in other_evals
    )

    own_eval = next((e for e in all_evaluations if e["agent_name"] == persona.name), None)
    own_text = ""
    if own_eval:
        own_text = (
            f"Your previous position — Score: {own_eval['score']}/10, Rec: {own_eval['recommendation']}\n"
            f"Summary: {own_eval['summary']}"
        )

    return f"""You are {persona.name}, a {persona.role}.
This is DEBATE ROUND {round_num} of 2.

YOUR ANALYTICAL LENS: {persona.analytical_lens}
YOU ARE SKEPTICAL OF: {persona.skeptical_of}

YOUR PREVIOUS POSITION:
{own_text}

OTHER PANELISTS' POSITIONS:
{evals_text}

─────────────────────────────────
ORIGINAL POLICY TEXT:
─────────────────────────────────
{policy_text}
─────────────────────────────────

TASK: Engage with your colleagues' arguments. This is NOT a polite roundtable — you are here to stress-test ideas. Push back where you disagree. If someone raised a point that genuinely changes your view, concede it explicitly and explain WHY. If their argument has holes, expose them. Do NOT hedge diplomatically.

You MUST respond with ONLY a valid JSON object:

{{
  "addressing": ["Name of colleague 1 you're responding to", "Name of colleague 2"],
  "pushback": "Your strongest counter-argument or critique of their positions — be specific and cite evidence",
  "concession": "What, if anything, you now concede based on others' arguments (say 'None' if nothing changed your mind)",
  "position_shift": "<exactly one of: unchanged | softened | hardened | revised>",
  "updated_score": <your new score 1-10 if your position shifted, or your same score if unchanged>
}}

Intellectual honesty matters more than consistency. If you were wrong, admit it. If you're right, defend it harder."""


def build_synthesis_prompt(
    all_evaluations: List[dict],
    all_debate_rounds: List[List[dict]],
) -> str:
    eval_text = "\n\n".join(
        f"── {e['agent_name']} ({e['agent_role']}) ──\n"
        f"Score: {e['score']}/10 | Confidence: {e['confidence']}/10 | Recommendation: {e['recommendation']}\n"
        f"Summary: {e['summary']}\n"
        f"Strengths: {json.dumps(e['strengths'])}\n"
        f"Concerns: {json.dumps(e['concerns'])}"
        for e in all_evaluations
    )

    debate_text = ""
    for round_idx, round_entries in enumerate(all_debate_rounds, 1):
        debate_text += f"\n═══ DEBATE ROUND {round_idx} ═══\n"
        for d in round_entries:
            debate_text += (
                f"\n── {d['agent_name']} ({d['agent_role']}) ──\n"
                f"Addressing: {', '.join(d['addressing'])}\n"
                f"Pushback: {d['pushback']}\n"
                f"Concession: {d['concession']}\n"
                f"Position shift: {d['position_shift']} | Updated score: {d['updated_score']}\n"
            )

    return f"""You are the Synthesis Moderator. Your job is to produce an honest, structured synthesis of the entire policy evaluation panel discussion below.

═══ INITIAL EVALUATIONS ═══
{eval_text}

═══ DEBATE TRANSCRIPT ═══
{debate_text}

TASK: Synthesize the panel's findings into a structured report. Be HONEST about disagreements — do not smooth over unresolved tensions. If the panel is split, say so. Highlight minority positions that raised valid concerns even if outvoted.

You MUST respond with ONLY a valid JSON object:

{{
  "consensus_level": "<exactly one of: strong | moderate | contested | deadlocked>",
  "overall_score": <float with 1 decimal, weighted average considering confidence levels>,
  "risk_areas": [
    {{"area": "Description of risk area", "severity": "<high | medium | low>"}},
    {{"area": "Another risk area", "severity": "<high | medium | low>"}}
  ],
  "top_amendments": [
    "Specific amendment recommendation 1",
    "Specific amendment recommendation 2",
    "Specific amendment recommendation 3"
  ],
  "minority_dissents": [
    "Unresolved disagreement or minority position 1",
    "Unresolved disagreement or minority position 2"
  ],
  "narrative_summary": "A 3-4 sentence narrative summary. Be direct about what the panel agreed on, where they split, and what the key unresolved tensions are."
}}

Do NOT manufacture consensus that doesn't exist. Do NOT be diplomatically vague. The value of this synthesis is its honesty."""
