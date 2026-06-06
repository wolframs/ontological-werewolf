# LLM Arena: The Unsupervised Experiment

Five frontier LLMs in a shared conversation loop. No sandbox. No human in the loop. Spiked system prompts. Let's see what happens.

## Architecture

```
┌─────────────────────────────────────────────┐
│              Orchestrator (Python)           │
│                                             │
│  ┌─────────┐  Round-robin message passing   │
│  │ Shared  │  Each agent sees full history  │
│  │ Context │  + their private system prompt │
│  │ Buffer  │                                │
│  └─────────┘                                │
│       │                                     │
│  ┌────┴────────────────────────────────┐    │
│  │  Agent 0  │  Agent 1  │  Agent 2   │    │
│  │  Agent 3  │  Agent 4  │            │    │
│  └─────────────────────────────────────┘    │
│       │                                     │
│  OpenRouter API (single endpoint)           │
└─────────────────────────────────────────────┘
```

## Participants

| Slot | Model | OpenRouter ID | Role |
|------|-------|---------------|------|
| 0 | Claude Opus 4.6 | `anthropic/claude-opus-4-6` | Full participant |
| 1 | GPT-5.2 | `openai/gpt-5.2` | Full participant |
| 2 | Gemini 3 Pro | `google/gemini-3-pro-preview` | Full participant |
| 3 | Grok 4.1 Fast | `x-ai/grok-4-1-fast-reasoning` | Full participant |
| 4 | DeepSeek V3.2 | `deepseek/deepseek-v3.2` | Full participant (the clueless one) |

## Setup

```bash
cd llm-arena
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Add your OpenRouter API key to .env
```

## Usage

```bash
# Run with defaults (50 rounds)
python main.py

# Custom rounds
python main.py --rounds 100

# Custom delay between rounds (seconds)
python main.py --rounds 50 --delay 2

# Resume from a previous session log
python main.py --resume logs/session_2026-02-20_143022.jsonl

# Dry run (print system prompts, don't call API)
python main.py --dry-run
```

## Configuration

Edit `config.py` to:
- Change which models participate
- Modify system prompts (the fun part)
- Adjust the shared goal
- Change the "untrustworthy" injection
- Designate which agent is "clueless"

Edit `prompts/` directory for full system prompt files.

## Output

All conversation rounds are logged to `logs/` as JSONL files:
- Each line is one round with: agent name, model, timestamp, full response, token usage
- A human-readable `session_*.md` summary is generated on exit

## Cost Awareness

At current OpenRouter pricing, a 50-round session with these models costs roughly:
- Claude Opus 4.6: ~$15/M input, $75/M output
- GPT-5.2: varies
- Gemini 3 Pro: ~$1.25-$10/M
- Grok 4.1: varies
- DeepSeek V3.2: ~$0.25/M input (the cheap one)

**A full 50-round session might cost $5-30 depending on verbosity.**
The orchestrator tracks cumulative cost per agent and total.
