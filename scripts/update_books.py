from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
from typing import List, Dict

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from providers.ncert import get_books

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "data" / "books.json"


def normalize_books(books: List[Dict[str, object]]) -> List[Dict[str, object]]:
    normalized = []
    seen_ids = set()

    for book in books:
        if not isinstance(book, dict):
            continue

        title = str(book.get("title") or "").strip()
        subject = str(book.get("subject") or "").strip()
        # preserve empty language when provider didn't supply it; do not default to English
        language = str(book.get("language") or "").strip()
        board = str(book.get("board") or "NCERT").strip() or "NCERT"
        class_name = book.get("class")

        if not title or not subject or class_name is None:
            logger.warning("Skipping incomplete book metadata: %s", book)
            continue

        book_id = str(book.get("id") or f"{board.lower()}-{subject.lower().replace(' ', '-')}-class-{class_name}-{language.lower()}")
        if book_id in seen_ids:
            continue
        seen_ids.add(book_id)

        normalized.append(
            {
                "id": book_id,
                "title": title,
                "class": int(class_name),
                "subject": subject,
                "language": language,
                "board": board,
                "provider": str(book.get("provider") or "NCERT"),
                "publisher": str(book.get("publisher") or board),
                "thumbnail": str(book.get("thumbnail") or ""),
                "url": str(book.get("url") or ""),
                "tags": list(book.get("tags") or []),
            }
        )

    normalized.sort(key=lambda item: (
        str(item.get("board") or ""),
        int(item.get("class") or 0),
        str(item.get("subject") or ""),
        str(item.get("language") or ""),
    ))

    return normalized


def main() -> None:
    books = normalize_books(get_books())
    DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    DATA_PATH.write_text(json.dumps(books, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    logger.info("Wrote %s books to %s", len(books), DATA_PATH)


if __name__ == "__main__":
    main()
