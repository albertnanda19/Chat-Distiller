from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

try:
    from extractor import ExtractError, extract_conversation_state
    from fetcher import FetchError, fetch_html
    from rebuilder import RebuildError, rebuild_messages
    from archive_builder import (
        ArchiveBuildError,
        build_archive,
        build_archive_from_file,
        merge_archives_from_files,
    )
    from storage import StorageError, store_archive
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from extractor import ExtractError, extract_conversation_state
    from fetcher import FetchError, fetch_html
    from rebuilder import RebuildError, rebuild_messages
    from archive_builder import (
        ArchiveBuildError,
        build_archive,
        build_archive_from_file,
        merge_archives_from_files,
    )
    from storage import StorageError, store_archive


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
        "--store",
        action="store_true",
        help="Store per-chat archive + metadata into data/<chat_title>/ (Phase 3)",
    )
    p.add_argument(
        "--merge",
        action="store_true",
        help="Merge two archive.json files into a new merged archive.json",
    )
    p.add_argument(
        "--input-a",
        default=None,
        help="First archive.json path (required with --merge)",
    )
    p.add_argument(
        "--input-b",
        default=None,
        help="Second archive.json path (required with --merge)",
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

    if args.merge:
        if not args.input_a or not args.input_b:
            print("--merge requires --input-a <archive_a.json> and --input-b <archive_b.json>", file=sys.stderr)
            return 2
        try:
            input_a = Path(args.input_a)
            input_b = Path(args.input_b)

            name_a = input_a.parent.name
            name_b = input_b.parent.name
            merged_dir = Path("data") / f"{name_a}__{name_b}"
            merged_dir.mkdir(parents=True, exist_ok=True)
            out_path = merged_dir / "archive.json"

            merge_archives_from_files(input_a, input_b, out_path)
        except ArchiveBuildError as e:
            print(str(e), file=sys.stderr)
            return 6
        print(str(merged_dir))
        return 0

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

    if args.store:
        if not args.url:
            print("--store requires --url <share_link>", file=sys.stderr)
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
            print(
                "Tip: re-run with --debug-html <file.html> to inspect the fetched page",
                file=sys.stderr,
            )
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

        try:
            archive = build_archive(messages)
        except ArchiveBuildError as e:
            print(str(e), file=sys.stderr)
            return 6

        try:
            stored_dir = store_archive(
                share_url=args.url,
                html=html,
                archive=archive,
                message_count=int(archive.get("meta", {}).get("total_messages", len(messages))),
            )
        except StorageError as e:
            print(str(e), file=sys.stderr)
            return 7

        print(str(stored_dir))
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