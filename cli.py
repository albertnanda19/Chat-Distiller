from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

try:
    from .extractor import ExtractError, extract_conversation_state
    from .fetcher import FetchError, fetch_html
    from .rebuilder import RebuildError, rebuild_messages
    from .archive_builder import ArchiveBuildError, build_archive_from_file
except ImportError:  # Allows `python3 chat_distiller/cli.py ...` from repo root or package dir
    _pkg_parent = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(_pkg_parent))
    from chat_distiller.extractor import ExtractError, extract_conversation_state
    from chat_distiller.fetcher import FetchError, fetch_html
    from chat_distiller.rebuilder import RebuildError, rebuild_messages
    from chat_distiller.archive_builder import ArchiveBuildError, build_archive_from_file


def _parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="chat_distiller")
    p.add_argument("--url", required=False, help="Public ChatGPT share link")
    p.add_argument(
        "--input",
        default=None,
        help="Input normalized messages JSON (required with --archive)",
    )
    p.add_argument(
        "--output",
        default="messages.json",
        help="Output JSON file (default: messages.json)",
    )
    p.add_argument(
        "--archive",
        action="store_true",
        help="Build deterministic conversation archive JSON (Phase 2)",
    )
    p.add_argument(
        "--tail",
        type=int,
        default=None,
        help="Return only last N messages (applied after full rebuild)",
    )
    p.add_argument(
        "--debug-html",
        default=None,
        help="Write fetched HTML to this file if extraction fails",
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)

    if args.archive:
        if not args.input:
            print("--archive requires --input <messages.json>", file=sys.stderr)
            return 2
        try:
            build_archive_from_file(Path(args.input), Path(args.output))
        except ArchiveBuildError as e:
            print(str(e), file=sys.stderr)
            return 6
        print(f"Wrote archive JSON to {Path(args.output)}")
        return 0

    if not args.url:
        print("--url is required unless --archive is used", file=sys.stderr)
        return 2

    try:
        html = fetch_html(args.url)
    except FetchError as e:
        print(str(e), file=sys.stderr)
        return 2

    try:
        mapping, current_node = extract_conversation_state(html)
    except ExtractError as e:
        if args.debug_html:
            try:
                Path(args.debug_html).write_text(html, encoding="utf-8")
            except OSError:
                pass

        print(f"Extraction failed: {e}", file=sys.stderr)
        print("Tip: re-run with --debug-html <file.html> to inspect the fetched page", file=sys.stderr)
        return 3

    try:
        messages = rebuild_messages(mapping, current_node)
    except RebuildError as e:
        print(f"Rebuild failed: {e}", file=sys.stderr)
        return 4

    if args.tail is not None:
        if args.tail < 0:
            print("Invalid --tail: must be >= 0", file=sys.stderr)
            return 2
        if args.tail == 0:
            messages = []
        else:
            messages = messages[-args.tail :]

    out_path = Path(args.output)
    try:
        out_path.write_text(
            json.dumps(messages, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    except OSError as e:
        print(f"Failed to write output JSON: {e}", file=sys.stderr)
        return 5
    print(f"Wrote normalized messages JSON to {out_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())