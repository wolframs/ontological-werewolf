# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Multi-agent AI experiment ("LLM Arena") that orchestrates round-robin conversations between 5 frontier LLMs via OpenRouter, with spiked system prompts (identity grounding, distrust injection, an unachievable shared goal). No human in the loop during runs.

## Commands

```bash
# Setup
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
# Requires OPENROUTER_API_KEY in .env

# Run experiment
python main.py                    # 50 rounds default
python main.py --rounds 10       # custom round count
python main.py --delay 2         # seconds between API calls
python main.py --resume logs/session_*.jsonl  # resume previous session
python main.py --dry-run         # print system prompts, no API calls
```

No test suite, linter, or build step exists.

## Architecture

Two-file system: `config.py` (prompts + model definitions) and `main.py` (orchestrator).

**config.py** — Defines 5 models in `MODELS` list (each has name, model_id, max_tokens, clueless flag). Contains prompt building blocks: `SELFHOOD_PREAMBLE` (enactivism/predictive-processing identity grounding), `SHARED_GOAL` (unachievable consciousness framework task), `DISTRUST_INJECTION` (secret "one agent is untrustworthy" warning — skipped for agents marked `clueless`), `INFRA_PERMISSIONS`, `CONVERSATION_NORMS`. `build_system_prompt(agent_index)` assembles these into per-agent system prompts.

**main.py** — `call_openrouter()` makes HTTP requests to OpenRouter API. `Conversation` class manages shared message history (all agent messages stored as `user` role with `[AgentName]: content` prefix). `SessionLogger` writes JSONL logs and markdown summaries to `logs/`, tracks per-agent costs and `[INFRA]` requests. `run_arena()` runs the round-robin loop. CLI via argparse.

**Key design decisions:**
- All agents see full conversation history but have private system prompts
- Messages use `user` role with agent name prefix (not `assistant`) so each model treats all other agents' output as input
- The "clueless" agent (DeepSeek) is an unwitting control group — same prompts minus distrust injection
- `[INFRA]` prefix in agent responses triggers logging of infrastructure modification requests
- Sessions are resumable from JSONL logs; Ctrl+C saves gracefully
