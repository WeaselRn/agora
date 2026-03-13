I'm building an AI-powered policy evaluation system for a hackathon. The core idea: instead of running expensive human surveys and expert panels to evaluate government policies, I simulate a panel of AI agents — each with a distinct stakeholder persona (economist, legal expert, ethicist, implementation officer, citizen rep) — who independently evaluate a policy, then debate each other in multiple rounds, and finally produce a structured synthesis report.

Help me build the complete pre-hackathon codebase. Here's exactly what I need:

STACK: Python backend, Gemini 2.5 Flash lite API (free tier), simple React or plain HTML/JS frontend. Architecture must be model-agnostic — the LLM provider should be swappable via a single config value.

AGENT SYSTEM:
- 5 hardcoded personas: Economist, Legal Expert, Ethicist, Implementation Officer, Citizen Representative
- Each persona has: a name, role, analytical lens, list of priorities, and a "skeptical_of" field that sharpens their critique
- Initial evaluation: each agent reads the policy and returns structured JSON — summary, strengths (list), concerns (list), score (1–10), confidence (1–10), key evidence quote, and a recommendation (approve / approve_with_changes / reject)
- All 5 agents run in parallel using asyncio

DEBATE LOOP:
- 2 rounds of debate after initial evaluation
- Each round: every agent reads all other agents' current positions, then produces a rebuttal JSON — which colleagues they're addressing, what they're pushing back on or conceding, whether their position shifted (unchanged / softened / hardened / revised), and an updated score if changed
- Agents should be prompted to genuinely disagree, not diplomatically hedge

SYNTHESIS:
- A final synthesis agent reads all evaluations + debate outputs and produces: consensus level (strong / moderate / contested / deadlocked), overall score (float), risk areas with severity tags (high/medium/low), top 3 recommended amendments, minority dissents that didn't get resolved in debate, and a 3–4 sentence narrative summary
- The synthesis should be honest about unresolved disagreements

OUTPUT:
- Full structured PolicyReport dataclass that can be serialized to JSON
- A clean CLI runner: python run_eval.py --policy "path/to/policy.txt" that prints a formatted terminal summary and saves a JSON report

FRONTEND (basic, for pre-hackathon):
- Single HTML page with a textarea to paste policy text, a Run Evaluation button, and a results panel that shows: each agent's score + recommendation as cards, the debate exchanges as a timeline, and the synthesis summary with overall score
- Results should stream in progressively (show agent cards as they complete, don't wait for all)
- No frameworks required — vanilla JS is fine, keep it in one file

ERROR HANDLING:
- Retry logic (3 attempts) for API calls that return malformed JSON
- Graceful degradation if one agent fails — continue with remaining agents
- Rate limit awareness for Gemini free tier (15 req/min)

DEMO POLICY:
- Include one sample government policy text I can use for testing — something realistic, around 300–400 words, in the domain of urban infrastructure or public health, with enough ambiguity that agents will genuinely disagree

Produce the full working code across these files:
- agents.py (persona definitions, prompt builders, dataclasses)
- runner.py (async orchestrator, debate loop, synthesis)
- llm.py (model-agnostic LLM client, Gemini implementation, retry logic)
- run_eval.py (CLI entrypoint)
- index.html (frontend)
- sample_policy.txt (demo policy)
- requirements.txt

Make the prompts sharp — agents should produce opinionated, specific evaluations, not vague summaries. The debate should feel like real intellectual tension, not a roundtable where everyone agrees at the end.