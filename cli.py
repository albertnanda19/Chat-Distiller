from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

try:
    from .extractor import ExtractError, extract_conversation_state
    from .fetcher import FetchError, fetch_html
    from .rebuilder import RebuildError, rebuild_messages
    from .compiler import CompileError, compile_context, generate_markdown_snapshot
except ImportError:  # Allows `python3 chat_distiller/cli.py ...` from repo root or package dir
    _pkg_parent = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(_pkg_parent))
    from chat_distiller.extractor import ExtractError, extract_conversation_state
    from chat_distiller.fetcher import FetchError, fetch_html
    from chat_distiller.rebuilder import RebuildError, rebuild_messages
    from chat_distiller.compiler import CompileError, compile_context, generate_markdown_snapshot


def _parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="chat_distiller")
    p.add_argument("--url", required=True, help="Public ChatGPT share link")
    p.add_argument(
        "--output",
        default="messages.json",
        help="Output JSON file (default: messages.json)",
    )
    p.add_argument(
        "--extract-context",
        action="store_true",
        help="Extract structured technical context using Gemini (Phase 2)",
    )
    p.add_argument(
        "--markdown",
        action="store_true",
        help="When used with --extract-context, output Markdown snapshot (Phase 3)",
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

    if args.markdown and not args.extract_context:
        print("--markdown requires --extract-context", file=sys.stderr)
        return 2

    if args.extract_context:
        try:
            structured = compile_context(messages)
        except CompileError as e:
            print(str(e), file=sys.stderr)
            return 6

        if args.markdown:
            out_path = Path(args.output)
            if args.output == "messages.json":
                out_path = Path("snapshot.md")
            try:
                md = generate_markdown_snapshot(structured)
            except Exception as e:
                print(f"Failed to generate markdown: {e}", file=sys.stderr)
                return 7
            try:
                out_path.write_text(md, encoding="utf-8")
            except OSError as e:
                print(f"Failed to write markdown: {e}", file=sys.stderr)
                return 5
            print(f"Wrote markdown snapshot to {out_path}")
            return 0

        out_path = Path(args.output)
        try:
            out_path.write_text(
                json.dumps(structured, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        except OSError as e:
            print(f"Failed to write output JSON: {e}", file=sys.stderr)
            return 5
        print(f"Wrote structured context JSON to {out_path}")
        return 0

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