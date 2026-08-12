"""Command line entry point: ``cogram-goai <command>``."""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import List, Optional

from cogram_goai import __version__
from cogram_goai.notes import NoteStore
from cogram_goai.pipeline import PipelineResult, approve_always, approve_never, run_pipeline
from cogram_goai.skill import SKILL_CONTRACT, keyword_recall
from cogram_goai.trace import Trace

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))
DEFAULT_NOTES = os.path.join(_REPO_ROOT, "examples", "notes.json")
DEFAULT_ISSUE = os.path.join(_REPO_ROOT, "examples", "issues", "flaky_upload_timeout.txt")


def _load_store(path: str) -> NoteStore:
    return NoteStore.load(path)


def _read_issue(args: argparse.Namespace) -> str:
    if getattr(args, "issue_file", None):
        with open(args.issue_file, "r", encoding="utf-8") as handle:
            return handle.read()
    if getattr(args, "issue", None):
        return args.issue
    with open(DEFAULT_ISSUE, "r", encoding="utf-8") as handle:
        return handle.read()


def _print_result(result: PipelineResult) -> None:
    print("run_id: %s" % result.run_id)
    print("\n[A1 triage] %d subtasks" % len(result.subtasks))
    for task in result.subtasks:
        print("  - %s (%s, budget %d) %s" % (task.id, task.kind, task.budget_steps, task.title))

    hits = result.recall.get("notes", [])
    print("\n[A2 memory] %d recalled note(s)" % len(hits))
    for note in hits:
        print("  - %s score=%.1f :: %s" % (note["id"], note["score"], note["text"]))
        print("      matched: %s" % (", ".join(note["matched"]) or "-"))
    if result.recall.get("fallback"):
        print("  fallback: %s" % result.recall["fallback"])

    print("\n[A3 verifier] %s" % ("all items passed" if result.verified else "incomplete"))
    for item in result.checklist:
        print("  [%s] %s <- %s" % ("x" if item.passed else " ", item.requirement, item.evidence))

    print("\n[gate] approved=%s" % result.approved)
    if result.captured_note_id:
        print("[memory] captured new note %s" % result.captured_note_id)


def _cmd_demo(args: argparse.Namespace) -> int:
    store = _load_store(args.notes)
    # Never let the demo mutate the checked-in example store.
    if os.path.abspath(args.notes) == os.path.abspath(DEFAULT_NOTES):
        store.path = os.path.join(os.getcwd(), "cogram_demo_notes.json")
    trace = Trace(path=args.trace)
    issue = _read_issue(args)
    evidence = {
        "t1": "reproduced locally with tests/fixtures/large_upload.bin",
        "t2": "narrowed to the retry wrapper in uploader",
        "t3": "patch + regression test drafted",
    }
    result = run_pipeline(
        issue,
        store,
        trace=trace,
        evidence=evidence,
        approve=approve_always if args.auto_approve else _interactive_approval,
        capture=not args.no_capture,
    )
    _print_result(result)
    if args.trace:
        print("\ntrace written to %s" % args.trace)
    else:
        print("\n--- trace (jsonl) ---")
        print(trace.as_jsonl())
    return 0


def _cmd_run(args: argparse.Namespace) -> int:
    store = _load_store(args.notes)
    trace = Trace(path=args.trace)
    evidence = json.loads(args.evidence) if args.evidence else None
    approve = approve_always if args.auto_approve else (approve_never if args.reject else _interactive_approval)
    result = run_pipeline(
        _read_issue(args),
        store,
        trace=trace,
        evidence=evidence,
        approve=approve,
        max_notes=args.max_notes,
        capture=not args.no_capture,
    )
    if args.json:
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    else:
        _print_result(result)
    return 0 if result.verified else 1


def _cmd_skill(args: argparse.Namespace) -> int:
    store = _load_store(args.notes)
    result = keyword_recall(_read_issue(args), notes=list(store), max_notes=args.max_notes)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def _cmd_contract(_: argparse.Namespace) -> int:
    print(json.dumps(SKILL_CONTRACT, ensure_ascii=False, indent=2))
    return 0


def _cmd_notes(args: argparse.Namespace) -> int:
    store = _load_store(args.notes)
    if args.add:
        note = store.append(args.add, tags=args.tag or [])
        store.save()
        print("added %s" % note.id)
        return 0
    for note in store:
        print("%-22s %-28s %s" % (note.id, ",".join(note.tags) or "-", note.text))
    print("\n%d note(s) in %s" % (len(store), store.path))
    return 0


def _interactive_approval(result: PipelineResult) -> bool:
    print("\n[gate] %d/%d checklist items passed." % (
        sum(1 for item in result.checklist if item.passed),
        len(result.checklist),
    ))
    if not sys.stdin.isatty():
        print("[gate] non-interactive stdin; treating as reject.")
        return False
    answer = input("Merge this run and capture a note? [y/N] ").strip().lower()
    return answer in {"y", "yes"}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="cogram-goai", description=__doc__)
    parser.add_argument("--version", action="version", version="cogram-goai %s" % __version__)
    sub = parser.add_subparsers(dest="command", required=True)

    def add_common(target: argparse.ArgumentParser) -> None:
        target.add_argument("--notes", default=DEFAULT_NOTES, help="path to the note store JSON")
        target.add_argument("--issue", help="issue text inline")
        target.add_argument("--issue-file", help="path to a file containing the issue text")

    demo = sub.add_parser("demo", help="run the bundled end-to-end example")
    add_common(demo)
    demo.add_argument("--trace", help="write the JSONL trace to this path")
    demo.add_argument("--auto-approve", action="store_true", help="skip the interactive gate")
    demo.add_argument("--no-capture", action="store_true", help="do not write a note back")
    demo.set_defaults(func=_cmd_demo)

    run = sub.add_parser("run", help="run the pipeline on your own issue")
    add_common(run)
    run.add_argument("--evidence", help='JSON map of subtask id -> evidence, e.g. \'{"t1":"repro log"}\'')
    run.add_argument("--trace", help="write the JSONL trace to this path")
    run.add_argument("--max-notes", type=int, default=3)
    run.add_argument("--auto-approve", action="store_true")
    run.add_argument("--reject", action="store_true", help="always reject at the gate")
    run.add_argument("--no-capture", action="store_true")
    run.add_argument("--json", action="store_true", help="emit the machine-readable result")
    run.set_defaults(func=_cmd_run)

    skill = sub.add_parser("skill", help="call cogram.keyword_recall directly")
    add_common(skill)
    skill.add_argument("--max-notes", type=int, default=3)
    skill.set_defaults(func=_cmd_skill)

    contract = sub.add_parser("contract", help="print the skill contract as JSON")
    contract.set_defaults(func=_cmd_contract)

    notes = sub.add_parser("notes", help="list or append notes")
    notes.add_argument("--notes", default=DEFAULT_NOTES)
    notes.add_argument("--add", help="append a note with this text")
    notes.add_argument("--tag", action="append", help="tag for the appended note (repeatable)")
    notes.set_defaults(func=_cmd_notes)

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
