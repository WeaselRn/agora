# Agora — AI Policy Evaluation System

**Agora** is an AI-powered policy analysis system that simulates a panel of expert stakeholders who evaluate, debate, and synthesize government policies.

Instead of relying on costly surveys and expert panels, Agora uses multiple AI agents — each representing a different perspective — to stress-test policies through structured debate.

The result is a **transparent, structured evaluation report** showing strengths, risks, disagreements, and recommended amendments.

---

# Concept

Public policy decisions are complex and affect multiple stakeholders.

Agora simulates this by creating **five AI agents**, each representing a different viewpoint:

| Agent                  | Perspective                            |
| ---------------------- | -------------------------------------- |
| Economist              | Fiscal sustainability, economic impact |
| Legal Expert           | Constitutional validity and regulation |
| Ethicist               | Fairness, justice, civil liberties     |
| Implementation Officer | Operational feasibility                |
| Citizen Representative | Real-world public impact               |

Each agent:

1. Independently evaluates the policy
2. Debates other agents across multiple rounds
3. Updates their position if persuaded
4. Contributes to a final synthesis report

This creates **intellectual tension and realistic critique**, rather than simple summaries.

---

# Features

• Multi-agent policy evaluation
• Structured JSON outputs
• Two rounds of agent debate
• Honest synthesis with disagreements preserved
• Progressive streaming results in the UI
• Model-agnostic architecture (LLM can be swapped)
• CLI and web interface
• Real-world evidence retrieval using Tavily search
• Automatic retry handling for malformed LLM responses

---

# System Architecture

```
Frontend (HTML + JS)
        │
        │  SSE Streaming
        ▼
FastAPI Server (runner.py)
        │
        ├── Agent Evaluation Phase
        │
        ├── Debate Loop (2 rounds)
        │
        ├── Policy Evidence Retrieval (Tavily)
        │
        ▼
LLM Client (llm.py)
        │
        ▼
Gemini API
```

Agents communicate through structured prompts and return **strict JSON outputs**.

---

# Project Structure

```
agora/
│
├── agents.py
│   Agent personas, dataclasses, and prompt builders
│
├── runner.py
│   Main orchestrator + FastAPI SSE server
│
├── llm.py
│   Model-agnostic LLM client (Gemini implementation)
│
├── research.py
│   Tavily search integration for policy evidence
│
├── run_eval.py
│   CLI interface for evaluating policies
│
├── index.html
│   Web interface with live streaming results
│
├── sample_policy.txt
│   Example policy for testing
│
├── requirements.txt
│   Python dependencies
│
└── report.json
    Example output report
```

---

# Installation

## 1. Clone the repository

```
git clone https://github.com/YOUR_USERNAME/agora.git
cd agora
```

---

## 2. Create a virtual environment

```
python -m venv venv
```

Activate it:

Windows

```
venv\Scripts\activate
```

Mac / Linux

```
source venv/bin/activate
```

---

## 3. Install dependencies

```
pip install -r requirements.txt
```

---

# Environment Variables

Create a `.env` file in the project root:

```
GEMINI_API_KEY=your_gemini_api_key
TAVILY_API_KEY=your_tavily_api_key
```

You can get keys from:

Gemini API
https://aistudio.google.com/apikey

Tavily API
https://tavily.com

---

# Running the Web App

Start the server:

```
uvicorn runner:app --port 8000
```

Open your browser:

```
http://localhost:8000
```

Paste a policy and click **Run Evaluation**.

Results will stream live as agents finish.

---

# Running via CLI

You can also run evaluations from the terminal.

```
python run_eval.py --policy sample_policy.txt
```

Example output:

```
✓ Economist — Score: 3/10 — reject
✓ Legal Expert — Score: 2/10 — reject
✓ Ethicist — Score: 1/10 — reject
...
```

A full JSON report will be saved as:

```
report.json
```

---

# Example Output

The final synthesis includes:

• Consensus level
• Overall policy score
• Major risk areas
• Recommended amendments
• Minority dissents

Example:

```
Consensus: STRONG
Overall Score: 1.0 / 10

Major Risks
- Constitutional privacy violations
- Fiscal instability
- Federal overreach

Recommended Amendments
1. Remove warrantless GPS tracking
2. Replace federal override authority
3. Increase EV transition support
```

---

# Technologies Used

• Python
• FastAPI
• Gemini API
• Tavily Search API
• Server Sent Events (SSE)
• Asyncio
• HTML & CSS

---

# Future Improvements

• Add more stakeholder personas
• Visual debate graphs
• Policy comparison mode
• Regional policy simulation
• Open-source LLM compatibility
• PDF export of reports

---

# License

MIT License

---

# Author

Built for a hackathon project exploring **AI-assisted public policy analysis**.

If you find this interesting, feel free to fork and improve it.
