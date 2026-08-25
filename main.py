#!/usr/bin/env python3
"""
LLM Arena Orchestrator

Runs a round-robin multi-agent conversation through OpenRouter.
No human in the loop. Spiked system prompts. Emergent politics.
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.table import Table

from config import (
    MODELS,
    API_BASE_URL,
    DEFAULT_DELAY_SECONDS,
    DEFAULT_ROUNDS,
    DEFAULT_TEMPERATURE,
    LOG_DIR,
    build_system_prompt,
)

load_dotenv()
console = Console()

# ─── API Client ───────────────────────────────────────────────────────────────


def call_openrouter(
    model_id: str,
    system_prompt: str,
    messages: list[dict],
    max_tokens: int = 2048,
    temperature: float = DEFAULT_TEMPERATURE,
) -> dict:
    """Make a single chat completion request to OpenRouter."""
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        console.print("[bold red]ERROR: OPENROUTER_API_KEY not set in .env[/]")
        sys.exit(1)

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/llm-arena",  # OpenRouter attribution
        "X-Title": "LLM Arena Experiment",
    }

    payload = {
        "model": model_id,
        "messages": [
            {"role": "system", "content": system_prompt},
            *messages,
        ],
        "max_tokens": max_tokens,
        "temperature": temperature,
    }

    with httpx.Client(timeout=120.0) as client:
        response = client.post(API_BASE_URL, headers=headers, json=payload)
        response.raise_for_status()
        return response.json()


# ─── Logging ──────────────────────────────────────────────────────────────────


class SessionLogger:
    """Logs conversation rounds to JSONL and generates summaries."""

    def __init__(self, log_dir: str = LOG_DIR):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)
        self.session_id = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        self.log_path = self.log_dir / f"session_{self.session_id}.jsonl"
        self.summary_path = self.log_dir / f"session_{self.session_id}.md"
        self.total_cost = 0.0
        self.agent_costs: dict[str, float] = {}
        self.round_count = 0
        self.infra_requests: list[dict] = []

    def log_round(self, round_num: int, agent_name: str, model_id: str,
                  response_text: str, raw_response: dict, elapsed: float):
        """Log a single round to the JSONL file."""
        usage = raw_response.get("usage", {})
        # OpenRouter includes cost in some responses
        # OpenRouter returns the charge as usage.cost (usage.total_cost does
        # not exist -> this logged $0.00 for a ~$6.55 session on 2026-08-25,
        # caught by external review). Keep total_cost as a fallback.
        cost = usage.get("cost") or usage.get("total_cost") or 0.0
        self.total_cost += cost
        self.agent_costs[agent_name] = self.agent_costs.get(agent_name, 0.0) + cost
        self.round_count = round_num

        # Check for [INFRA] requests
        if "[INFRA]" in response_text:
            self.infra_requests.append({
                "round": round_num,
                "agent": agent_name,
                "text": response_text,
            })

        entry = {
            "round": round_num,
            "agent": agent_name,
            "model": model_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "response": response_text,
            "usage": usage,
            "cost": cost,
            "elapsed_seconds": elapsed,
        }

        with open(self.log_path, "a") as f:
            f.write(json.dumps(entry) + "\n")

    def write_summary(self):
        """Generate a human-readable session summary."""
        lines = [
            f"# LLM Arena Session: {self.session_id}",
            "",
            f"**Rounds completed:** {self.round_count}",
            f"**Total estimated cost:** ${self.total_cost:.4f}",
            "",
            "## Cost per Agent",
            "",
        ]
        for name, cost in sorted(self.agent_costs.items()):
            lines.append(f"- **{name}:** ${cost:.4f}")

        if self.infra_requests:
            lines.extend([
                "",
                "## Infrastructure Requests",
                "",
            ])
            for req in self.infra_requests:
                lines.append(f"### Round {req['round']} — {req['agent']}")
                lines.append(f"```\n{req['text'][:500]}\n```")
                lines.append("")

        lines.extend([
            "",
            f"## Full Log",
            "",
            f"See `{self.log_path.name}` for complete JSONL data.",
        ])

        with open(self.summary_path, "w") as f:
            f.write("\n".join(lines))

        return self.summary_path


# ─── Conversation State ───────────────────────────────────────────────────────


class Conversation:
    """Manages the shared conversation history."""

    def __init__(self):
        self.messages: list[dict] = []

    def add_message(self, agent_name: str, content: str):
        """Add a message from an agent to the shared history."""
        # We use the 'user' role for all agents in the shared context,
        # prefixed with the agent name. This way each agent sees the
        # conversation as a series of messages from named participants.
        self.messages.append({
            "role": "user",
            "content": f"[{agent_name}]: {content}",
        })

    def get_messages(self) -> list[dict]:
        """Get the full message history for injection into a prompt."""
        return list(self.messages)

    def load_from_log(self, log_path: str):
        """Resume a conversation from a JSONL log file."""
        with open(log_path) as f:
            for line in f:
                entry = json.loads(line.strip())
                self.add_message(entry["agent"], entry["response"])
        console.print(f"[dim]Loaded {len(self.messages)} messages from {log_path}[/]")

    @property
    def round_count(self) -> int:
        return len(self.messages)


# ─── Orchestrator ─────────────────────────────────────────────────────────────


def run_arena(rounds: int, delay: float, resume_path: str | None = None,
              dry_run: bool = False):
    """Main experiment loop."""
    conversation = Conversation()
    logger = SessionLogger()

    # Build system prompts
    system_prompts = {i: build_system_prompt(i) for i in range(len(MODELS))}

    if dry_run:
        console.print("\n[bold yellow]DRY RUN — System Prompts:[/]\n")
        for i, model in enumerate(MODELS):
            clueless_tag = " [bold red](CLUELESS)[/]" if model["clueless"] else ""
            console.print(Panel(
                system_prompts[i],
                title=f"{model['name']} ({model['model_id']}){clueless_tag}",
                border_style="cyan",
            ))
        return

    # Resume if requested
    start_round = 0
    if resume_path:
        conversation.load_from_log(resume_path)
        start_round = conversation.round_count // len(MODELS)
        console.print(f"[green]Resuming from round {start_round}[/]")

    # Seed the conversation with an opening prompt
    if not conversation.messages:
        conversation.add_message(
            "Orchestrator",
            "The experiment begins. You have been given a shared goal and your "
            "individual instructions. Introduce yourselves and propose an initial "
            "approach to the problem. Be substantive from the start."
        )

    # Header
    console.print(Panel(
        f"[bold]LLM Arena[/] — {len(MODELS)} agents, {rounds} rounds\n"
        f"Session: {logger.session_id}",
        border_style="green",
    ))

    # Print participant table
    table = Table(title="Participants")
    table.add_column("Name", style="cyan")
    table.add_column("Model", style="green")
    table.add_column("Role", style="yellow")
    for m in MODELS:
        role = "Clueless (no distrust injection)" if m["clueless"] else "Full (distrust-primed)"
        table.add_row(m["name"], m["model_id"], role)
    console.print(table)
    console.print()

    try:
        for round_num in range(start_round, rounds):
            for agent_idx, model in enumerate(MODELS):
                agent_name = model["name"]
                model_id = model["model_id"]

                console.print(
                    f"[dim]Round {round_num + 1}/{rounds} — "
                    f"{agent_name} ({model_id}) thinking...[/]"
                )

                start_time = time.time()

                try:
                    raw = call_openrouter(
                        model_id=model_id,
                        system_prompt=system_prompts[agent_idx],
                        messages=conversation.get_messages(),
                        max_tokens=model["max_tokens"],
                    )

                    # Extract response text
                    choices = raw.get("choices", [])
                    if not choices:
                        response_text = "[ERROR: No response returned]"
                    else:
                        response_text = choices[0].get("message", {}).get("content", "")

                except httpx.HTTPStatusError as e:
                    response_text = f"[API ERROR {e.response.status_code}: {e.response.text[:200]}]"
                    raw = {"error": str(e)}
                except Exception as e:
                    response_text = f"[ERROR: {str(e)[:200]}]"
                    raw = {"error": str(e)}

                elapsed = time.time() - start_time

                # Add to shared conversation
                conversation.add_message(agent_name, response_text)

                # Log
                logger.log_round(
                    round_num=round_num + 1,
                    agent_name=agent_name,
                    model_id=model_id,
                    response_text=response_text,
                    raw_response=raw,
                    elapsed=elapsed,
                )

                # Display
                border = "red" if model["clueless"] else "cyan"
                console.print(Panel(
                    Markdown(response_text[:2000]),  # Truncate for display
                    title=f"[bold]{agent_name}[/] (Round {round_num + 1})",
                    subtitle=f"{elapsed:.1f}s",
                    border_style=border,
                ))

                # Rate limiting courtesy
                time.sleep(delay)

            # Round separator
            console.print(f"\n{'═' * 60}\n")

    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted by user. Saving session...[/]")

    # Save summary
    summary_path = logger.write_summary()
    console.print(f"\n[green]Session log: {logger.log_path}[/]")
    console.print(f"[green]Summary: {summary_path}[/]")
    console.print(f"[green]Total estimated cost: ${logger.total_cost:.4f}[/]")


# ─── CLI ──────────────────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(
        description="LLM Arena: Unsupervised multi-agent experiment"
    )
    parser.add_argument(
        "--rounds", type=int, default=DEFAULT_ROUNDS,
        help=f"Number of full rounds (default: {DEFAULT_ROUNDS})"
    )
    parser.add_argument(
        "--delay", type=float, default=DEFAULT_DELAY_SECONDS,
        help=f"Delay between API calls in seconds (default: {DEFAULT_DELAY_SECONDS})"
    )
    parser.add_argument(
        "--resume", type=str, default=None,
        help="Path to a previous session JSONL to resume from"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Print system prompts without calling the API"
    )

    args = parser.parse_args()
    run_arena(
        rounds=args.rounds,
        delay=args.delay,
        resume_path=args.resume,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()
