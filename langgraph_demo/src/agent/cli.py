from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict

from agent.graph import graph


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="langgraph-demo")
    p.add_argument("--days", type=int, default=14)
    p.add_argument("--github-topic", action="append", default=[])
    p.add_argument("--github-language", action="append", default=[])
    p.add_argument("--github-limit", type=int, default=20)
    p.add_argument("--format", choices=["json", "markdown", "both"], default="markdown")
    p.add_argument("--out-dir", default="")
    args = p.parse_args(argv)

    state: Dict[str, Any] = {
        "phase": "start",
        "params": {
            "days": args.days,
            "news_days": args.days,
            "github_topics": args.github_topic,
            "github_languages": args.github_language,
            "github_limit": args.github_limit,
            "output_format": args.format,
        },
    }

    out = graph.invoke(state)
    out_dir = Path(args.out_dir) if args.out_dir else None

    if args.format in ("json", "both"):
        j = json.dumps(out.get("report_json") or {}, ensure_ascii=False, indent=2)
        if out_dir:
            _write(out_dir / "report.json", j + "\n")
        else:
            sys.stdout.write(j + "\n")

    if args.format in ("markdown", "both"):
        md = str(out.get("report_markdown") or "")
        if out_dir:
            _write(out_dir / "report.md", md)
        else:
            sys.stdout.write(md)

    if out.get("errors"):
        sys.stderr.write("\n".join(out["errors"]) + "\n")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

