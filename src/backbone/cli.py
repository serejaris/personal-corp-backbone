from __future__ import annotations

import argparse
import json
import sys

from .pipeline import PipelineError, run
from .tasks import TaskError, done_task, load_tasks, start_task, verify_task


def cmd_task_list(_: argparse.Namespace) -> int:
    tasks = load_tasks()
    for t in tasks:
        mark = "x" if t.checked else " "
        print(f"[{mark}] {t.task_id} | {t.status:11} | {t.title}")
    return 0


def cmd_task_start(args: argparse.Namespace) -> int:
    t = start_task(args.task_id)
    print(f"Started {t.task_id}: {t.title}")
    return 0


def cmd_task_verify(args: argparse.Namespace) -> int:
    data = verify_task(args.task_id)
    print(json.dumps(data, ensure_ascii=False, indent=2))
    return 0


def cmd_task_done(args: argparse.Namespace) -> int:
    t = done_task(args.task_id)
    print(f"Done {t.task_id}: {t.title}")
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    rr = run(profile=args.profile, source=args.source)
    print(json.dumps({
        "artifact_id": rr.artifact_id,
        "artifact_path": rr.artifact_path,
        "request_id": rr.request_id,
    }, ensure_ascii=False))
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="backbone")
    sub = p.add_subparsers(dest="cmd", required=True)

    task = sub.add_parser("task")
    task_sub = task.add_subparsers(dest="task_cmd", required=True)

    tl = task_sub.add_parser("list")
    tl.set_defaults(func=cmd_task_list)

    ts = task_sub.add_parser("start")
    ts.add_argument("task_id")
    ts.set_defaults(func=cmd_task_start)

    tv = task_sub.add_parser("verify")
    tv.add_argument("task_id")
    tv.set_defaults(func=cmd_task_verify)

    td = task_sub.add_parser("done")
    td.add_argument("task_id")
    td.set_defaults(func=cmd_task_done)

    r = sub.add_parser("run")
    r.add_argument("--profile", required=True)
    r.add_argument("--source", required=True)
    r.set_defaults(func=cmd_run)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        return args.func(args)
    except (TaskError, PipelineError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
