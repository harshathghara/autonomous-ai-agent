"""CLI entry point — run a natural-language task through the agent and print the answer."""

import argparse
import asyncio
import json
import sys
import uuid

from dotenv import load_dotenv

load_dotenv()

_PREVIEW_LEN = 2000


def _format_tool_args(args: dict) -> str:
    try:
        return json.dumps(args, indent=2, ensure_ascii=False)
    except TypeError:
        return str(args)


def _preview(text: str, max_len: int = _PREVIEW_LEN) -> str:
    text = str(text)
    if len(text) <= max_len:
        return text
    return text[:max_len] + "\n... (truncated)"


def print_verbose_trace(messages: list) -> None:
    """Print each LLM thought, tool call, and tool result."""
    from agent.runner import messages_to_events

    print("\n========== Agent trace ==========")
    for event in messages_to_events(messages):
        if event["type"] == "thought":
            print(f"\n[Thought]\n{_preview(event['content'], 800)}")
        elif event["type"] == "tool_call":
            print(f"\n[Tool call] {event['name']}")
            print(f"  Input:\n{_format_tool_args(event['input'])}")
        elif event["type"] == "tool_result":
            print(f"\n[Tool result] {event['name']}")
            print(_preview(event["content"]))
    print("\n================================\n")


async def run(
    prompt: str,
    *,
    task_id: uuid.UUID | None = None,
    resume: bool = False,
    auto_approve: bool = False,
) -> tuple[str, list, uuid.UUID]:
    from agent.runner import run_agent_task

    return await run_agent_task(
        prompt,
        task_id=task_id,
        resume=resume,
        auto_approve=auto_approve,
    )


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="Run the autonomous AI agent")
    parser.add_argument("prompt", nargs="?", default="", help="Natural-language task for the agent")
    parser.add_argument("-v", "--verbose", action="store_true", help="Print each tool call and result")
    parser.add_argument(
        "-y",
        "--yes",
        action="store_true",
        help="Skip confirmation prompts for email send and calendar write/delete",
    )
    parser.add_argument("--resume", action="store_true", help="Resume a previously interrupted task")
    parser.add_argument("--task-id", type=str, help="Task UUID (required with --resume)")
    args = parser.parse_args()

    if args.resume and not args.task_id:
        parser.error("--resume requires --task-id")
    if not args.resume and not args.prompt:
        parser.error("prompt is required unless using --resume")

    task_uuid = uuid.UUID(args.task_id) if args.task_id else None
    prompt = args.prompt or "(resumed task)"

    print(f"Running agent: {prompt}\n")
    answer, messages, task_id = asyncio.run(
        run(prompt, task_id=task_uuid, resume=args.resume, auto_approve=args.yes)
    )
    if args.verbose:
        print_verbose_trace(messages)
    print("--- Final answer ---\n")
    print(answer)
    print(f"\nTask saved: {task_id}")


if __name__ == "__main__":
    main()
