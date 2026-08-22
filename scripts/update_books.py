from __future__ import annotations

import argparse
import json
import re
import shutil
from pathlib import Path
from typing import Dict, List, Tuple


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

ROOT = Path(__file__).resolve().parents[1]

DATA_PATH = ROOT / "data" / "books.json"
AUDIT_PATH = ROOT / "scripts" / "ncert_legacy_final_audit.txt"
BACKUP_PATH = ROOT / "data" / "books.json.backup"


# ---------------------------------------------------------------------------
# JSON helpers
# ---------------------------------------------------------------------------

def load_json(path: Path) -> List[Dict[str, object]]:
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        raise ValueError(f"{path} must contain a JSON list.")

    return data


# ---------------------------------------------------------------------------
# Audit parser
# ---------------------------------------------------------------------------

def parse_audit(path: Path) -> Dict[str, Dict[str, object]]:
    """
    Parse the actual NCERT audit format:

        OK | ncert-aeen1 | Marigold | HTTP=200 | SIZE=538945 | TYPE=text/html | https://...

    Also accepts:

        DEAD | ncert-example | Example | HTTP=404 | ...

        REDIRECT | ncert-example | Example | HTTP=301 | ... | https://...

        ERROR | ncert-example | Example | ...

    Returns:

        {
            "ncert-aeen1": {
                "title": "Marigold",
                "status": "OK",
                "http": 200,
                "final_url": "https://..."
            }
        }
    """

    if not path.exists():
        raise FileNotFoundError(f"Audit file not found: {path}")

    text = path.read_text(
        encoding="utf-8",
        errors="replace",
    )

    results: Dict[str, Dict[str, object]] = {}

    # -----------------------------------------------------------------------
    # The important part:
    #
    # Your audit file uses:
    #
    # STATUS | ID | TITLE | HTTP=XXX | ... | URL
    #
    # So parse line-by-line instead of trying to parse the old
    # [001/103] format.
    # -----------------------------------------------------------------------

    for raw_line in text.splitlines():

        line = raw_line.strip()

        if not line:
            continue

        # Ignore headers/separators.
        if line.startswith("="):
            continue

        # Expected minimum:
        #
        # OK | ncert-aeen1 | Marigold | HTTP=200 | ...
        #
        parts = [
            part.strip()
            for part in line.split("|")
        ]

        if len(parts) < 3:
            continue

        status = parts[0].upper()

        if status not in {
            "OK",
            "DEAD",
            "REDIRECT",
            "ERROR",
        }:
            continue

        book_id = parts[1].strip()

        if not book_id.startswith("ncert-"):
            continue

        title = parts[2].strip()

        # -------------------------------------------------------------------
        # HTTP status
        # -------------------------------------------------------------------

        http_status = None

        for part in parts[3:]:
            match = re.search(
                r"\bHTTP\s*=\s*(\d+)\b",
                part,
                re.IGNORECASE,
            )

            if match:
                http_status = int(match.group(1))
                break

        # -------------------------------------------------------------------
        # Find final URL.
        #
        # We deliberately search every field because the URL may be the
        # final field, but we don't want to depend on that forever.
        # -------------------------------------------------------------------

        final_url = ""

        for part in parts[3:]:
            candidate = part.strip()

            # Remove Markdown URL wrapper if present:
            #
            # [https://example.com](https://example.com)
            #
            markdown_match = re.match(
                r"^\[([^\]]+)\]\(([^)]+)\)$",
                candidate,
                re.IGNORECASE,
            )

            if markdown_match:
                candidate = markdown_match.group(2).strip()

            # Plain URL
            url_match = re.search(
                r"https?://[^\s\])]+",
                candidate,
                re.IGNORECASE,
            )

            if url_match:
                final_url = url_match.group(0).strip()

                # Remove accidental trailing punctuation.
                final_url = final_url.rstrip(
                    ".,;\"'"
                )

                break

        results[book_id] = {
            "title": title,
            "status": status,
            "http": http_status,
            "final_url": final_url,
        }

    return results


# ---------------------------------------------------------------------------
# Backup
# ---------------------------------------------------------------------------

def backup_books() -> None:
    if not DATA_PATH.exists():
        raise FileNotFoundError(
            f"Cannot create backup because books.json does not exist: "
            f"{DATA_PATH}"
        )

    if BACKUP_PATH.exists():
        BACKUP_PATH.unlink()

    shutil.copy2(
        DATA_PATH,
        BACKUP_PATH,
    )


# ---------------------------------------------------------------------------
# Update books
# ---------------------------------------------------------------------------

def update_books(
    books: List[Dict[str, object]],
    audit: Dict[str, Dict[str, object]],
    remove_dead: bool = False,
) -> Tuple[
    List[Dict[str, object]],
    int,
    int,
    int,
    int,
]:
    """
    Update only books present in the verified audit.

    Returns:

        updated_books
        changed_count
        dead_count
        removed_count
        unmatched_audit_count
    """

    changed = 0
    dead = 0
    removed = 0

    matched_audit_ids = set()

    updated_books: List[Dict[str, object]] = []

    for book in books:

        # Preserve malformed/non-dict records instead of destroying them.
        if not isinstance(book, dict):
            updated_books.append(book)
            continue

        book_id = str(
            book.get("id") or ""
        ).strip()

        # Not an audited NCERT book.
        if book_id not in audit:
            updated_books.append(book)
            continue

        matched_audit_ids.add(book_id)

        result = audit[book_id]

        status = str(
            result.get("status") or "UNKNOWN"
        ).upper()

        final_url = str(
            result.get("final_url") or ""
        ).strip()

        old_url = str(
            book.get("url") or ""
        ).strip()

        title = str(
            book.get("title") or ""
        )

        # -------------------------------------------------------------------
        # DEAD
        # -------------------------------------------------------------------

        if status == "DEAD":

            dead += 1

            print(
                f"DEAD    {book_id}: {title}"
            )

            if remove_dead:

                print(
                    "        -> REMOVED"
                )

                removed += 1
                changed += 1

                continue

            print(
                "        -> KEPT unchanged"
            )

            updated_books.append(book)
            continue

        # -------------------------------------------------------------------
        # ERROR
        # -------------------------------------------------------------------

        if status == "ERROR":

            print(
                f"ERROR   {book_id}: {title}"
            )

            print(
                "        -> KEPT unchanged"
            )

            updated_books.append(book)
            continue

        # -------------------------------------------------------------------
        # OK / REDIRECT
        # -------------------------------------------------------------------

        if status in {
            "OK",
            "REDIRECT",
        }:

            if not final_url:

                print(
                    f"WARNING {book_id}: {title}"
                )

                print(
                    "        -> Audit has no final URL; "
                    "kept unchanged"
                )

                updated_books.append(book)
                continue

            if old_url != final_url:

                book["url"] = final_url

                changed += 1

                print(
                    f"UPDATE  {book_id}: {title}"
                )

                print(
                    f"        OLD: {old_url}"
                )

                print(
                    f"        NEW: {final_url}"
                )

            updated_books.append(book)
            continue

        # -------------------------------------------------------------------
        # Unknown status
        # -------------------------------------------------------------------

        print(
            f"WARNING {book_id}: unknown audit status "
            f"{status!r}; kept unchanged"
        )

        updated_books.append(book)

    unmatched = len(
        set(audit.keys()) - matched_audit_ids
    )

    return (
        updated_books,
        changed,
        dead,
        removed,
        unmatched,
    )


# ---------------------------------------------------------------------------
# Write JSON
# ---------------------------------------------------------------------------

def write_books(
    books: List[Dict[str, object]],
) -> None:

    DATA_PATH.write_text(
        json.dumps(
            books,
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:

    parser = argparse.ArgumentParser(
        description=(
            "Update BUDH India's books.json using "
            "the verified NCERT legacy URL audit."
        )
    )

    parser.add_argument(
        "--remove-dead",
        action="store_true",
        help=(
            "Remove books whose audited NCERT URL "
            "is marked DEAD."
        ),
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help=(
            "Show changes without modifying books.json."
        ),
    )

    args = parser.parse_args()

    # -----------------------------------------------------------------------
    # Header
    # -----------------------------------------------------------------------

    print("=" * 80)
    print(
        "        BUDH INDIA — NCERT BOOK URL UPDATER"
    )
    print("=" * 80)
    print()

    print(
        f"Books: {DATA_PATH}"
    )

    print(
        f"Audit: {AUDIT_PATH}"
    )

    print()

    # -----------------------------------------------------------------------
    # Load
    # -----------------------------------------------------------------------

    books = load_json(DATA_PATH)

    audit = parse_audit(AUDIT_PATH)

    print(
        f"Existing books : {len(books)}"
    )

    print(
        f"Audit entries  : {len(audit)}"
    )

    print()

    # -----------------------------------------------------------------------
    # Safety check
    # -----------------------------------------------------------------------

    if not audit:

        raise RuntimeError(
            "No audit entries were parsed. "
            "Refusing to modify books.json."
        )

    # -----------------------------------------------------------------------
    # Show audit statistics
    # -----------------------------------------------------------------------

    ok_count = sum(
        1
        for item in audit.values()
        if item["status"] == "OK"
    )

    redirect_count = sum(
        1
        for item in audit.values()
        if item["status"] == "REDIRECT"
    )

    dead_count = sum(
        1
        for item in audit.values()
        if item["status"] == "DEAD"
    )

    error_count = sum(
        1
        for item in audit.values()
        if item["status"] == "ERROR"
    )

    print(
        f"OK audits       : {ok_count}"
    )

    print(
        f"Redirect audits : {redirect_count}"
    )

    print(
        f"Dead audits     : {dead_count}"
    )

    print(
        f"Error audits    : {error_count}"
    )

    print()

    # -----------------------------------------------------------------------
    # Update
    # -----------------------------------------------------------------------

    (
        updated_books,
        changed,
        dead,
        removed,
        unmatched,
    ) = update_books(
        books,
        audit,
        remove_dead=args.remove_dead,
    )

    # -----------------------------------------------------------------------
    # Summary
    # -----------------------------------------------------------------------

    print()

    print("=" * 80)
    print("FINAL SUMMARY")
    print("=" * 80)

    print(
        f"Audit entries       : {len(audit)}"
    )

    print(
        f"Books loaded        : {len(books)}"
    )

    print(
        f"URL changes         : {changed}"
    )

    print(
        f"Dead entries        : {dead}"
    )

    print(
        f"Removed             : {removed}"
    )

    print(
        f"Unmatched audits    : {unmatched}"
    )

    print(
        f"Final book count    : {len(updated_books)}"
    )

    print()

    # -----------------------------------------------------------------------
    # Dry run
    # -----------------------------------------------------------------------

    if args.dry_run:

        print(
            "DRY RUN — books.json was NOT modified."
        )

        print("=" * 80)

        return

    # -----------------------------------------------------------------------
    # Nothing changed
    # -----------------------------------------------------------------------

    if changed == 0:

        print(
            "No changes required. "
            "books.json was NOT rewritten."
        )

        print("=" * 80)

        return

    # -----------------------------------------------------------------------
    # Backup BEFORE writing
    # -----------------------------------------------------------------------

    backup_books()

    print(
        f"Backup created: {BACKUP_PATH}"
    )

    # -----------------------------------------------------------------------
    # Write
    # -----------------------------------------------------------------------

    write_books(updated_books)

    print(
        f"Updated: {DATA_PATH}"
    )

    print()

    print(
        "DONE."
    )

    print("=" * 80)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    main()