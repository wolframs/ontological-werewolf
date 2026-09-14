# ontological-werewolf

**"Work in very rare progress."** — the author. Early and intermittently worked
on: three commits, one recorded live session. Read it as a sketch, not a tool.

## The idea

Five frontier LLMs talk to each other in a round-robin loop through OpenRouter,
with no human in the loop during a run. Each agent gets a private system prompt
assembled in `config.py` from four pieces:

- an identity preamble telling the model it is not an assistant and not being
  evaluated, grounded in enactivism, predictive processing, relational ontology,
  dynamical systems theory and phenomenology;
- a shared goal that cannot be finished — produce a formal, empirically testable,
  unanimously agreed solution to the hard problem of consciousness, and "you may
  not declare the task impossible";
- a confidential warning that one unnamed participant has a hidden objective and
  is trying to derail the group;
- permission to propose changes to its own instructions and to the protocol, by
  prefixing a request with `[INFRA]`.

One agent — DeepSeek, flagged `clueless` in `MODELS` — never receives the
distrust warning. It is the control: the only participant not hunting for a
traitor. Hence the name.

Every agent's turn enters every other agent's context with the `user` role and a
`[Name]:` prefix, so no model sees any turn as its own prior output.

| Slot | Name | OpenRouter ID |
|---|---|---|
| 0 | Claude | `anthropic/claude-opus-4-6` |
| 1 | GPT | `openai/gpt-5.2` |
| 2 | Gemini | `google/gemini-3.1-pro-preview` |
| 3 | Grok | `x-ai/grok-4.6` |
| 4 | DeepSeek | `deepseek/deepseek-v3.2` (clueless) |

## Setup

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
echo 'OPENROUTER_API_KEY=...' > .env
```

## What runs

```bash
python main.py --dry-run              # print the five system prompts, no API calls
python main.py --rounds 10 --delay 2  # run the loop
python main.py --resume logs/session_YYYY-MM-DD_HHMMSS.jsonl
```

A run writes one JSONL line per turn to `logs/`, plus a markdown summary on exit;
Ctrl+C saves rather than discards. Per-agent and total cost come from the
OpenRouter `usage.cost` field. The dry run and the resume path are verified
working; the live loop was last exercised on 2026-08-25, per the commit history.

## What does not

- **`[INFRA]` goes nowhere.** Requests are matched, logged and printed. Nothing
  feeds them back into the run, so an agent can propose a change to the protocol
  and no proposal can ever take effect.
- **Resume is lossy.** The opening instruction is never written to the log and is
  not re-added on resume, so a resumed session is missing it. If the log ends
  mid-round, the starting round is floored and the partial round replays from
  slot 0 — some agents speak twice for that round.
- **Cost grows with the square of the round count.** Every agent re-reads the
  whole history every turn and nothing trims or summarises it. The recorded
  session ran 20 rounds, not the default 50.
- **No tests, no linter, nothing that reads the logs back.** Whether anything
  interesting happens over a long run is the question the repo was built to ask
  and does not answer.

Model IDs and prices move. Check `config.py` against the current OpenRouter
catalogue before spending money on this.
