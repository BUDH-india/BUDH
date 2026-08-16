from __future__ import annotations

import hashlib
import logging
import re
from typing import Dict, List, Optional, Tuple
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


logger = logging.getLogger(__name__)

NCERT_TEXTBOOK_URL = "https://ncert.nic.in/textbook.php"


# ---------------------------------------------------------------------------
# Controlled vocabularies
# ---------------------------------------------------------------------------

LANGUAGE_MAP = {
    "english": "English",
    "hindi": "Hindi",
    "urdu": "Urdu",
    "assamese": "Assamese",
    "bengali": "Bengali",
    "bodo": "Bodo",
    "dogri": "Dogri",
    "gujarati": "Gujarati",
    "kannada": "Kannada",
    "kashmiri": "Kashmiri",
    "konkani": "Konkani",
    "maithili": "Maithili",
    "malayalam": "Malayalam",
    "manipuri": "Manipuri",
    "marathi": "Marathi",
    "nepali": "Nepali",
    "odia": "Odia",
    "oriya": "Odia",
    "punjabi": "Punjabi",
    "sanskrit": "Sanskrit",
    "santhali": "Santhali",
    "sindhi": "Sindhi",
    "tamil": "Tamil",
    "telugu": "Telugu",
}

SUBJECT_ALIASES = {
    "bhugol": "Geography",
    "geography": "Geography",
    "itihas": "History",
    "history": "History",
    "ganit": "Mathematics",
    "mathematics": "Mathematics",
    "vigyan": "Science",
    "science": "Science",
    "evs": "Environmental Studies",
    "environmental studies": "Environmental Studies",
    "agriculture": "Agriculture",
}


# ---------------------------------------------------------------------------
# Basic helpers
# ---------------------------------------------------------------------------

def _normalize_text(value: Optional[str]) -> str:
    if not value:
        return ""
    return re.sub(r"\s+", " ", value).strip()


def _canonical_language(value: Optional[str]) -> str:
    value = _normalize_text(value)
    if not value:
        return ""
    return LANGUAGE_MAP.get(value.lower(), "")


def _canonical_subject(value: Optional[str]) -> str:
    value = _normalize_text(value)
    if not value:
        return ""
    return SUBJECT_ALIASES.get(value.lower(), value)


def _build_tags(
    title: str,
    class_name: Optional[int],
    subject: str,
    language: str,
) -> List[str]:
    tags: List[str] = []

    for word in re.findall(r"[a-zA-Z0-9]+", title.lower()):
        if len(word) > 2 and word not in {"the", "for", "and", "with"}:
            tags.append(word)

    if class_name is not None:
        tags.extend([f"class {class_name}", f"grade {class_name}"])

    if subject:
        tags.append(subject.lower())

    if language:
        tags.append(language.lower())

    tags.extend(["ncert", "textbook"])
    return list(dict.fromkeys(tags))


def _remove_parenthetical(value: str) -> str:
    return _normalize_text(re.sub(r"\s*\([^()]*\)\s*", " ", value))


def _build_thumbnail(source_key: Optional[str]) -> str:
    if not source_key:
        return ""
    return urljoin(
        NCERT_TEXTBOOK_URL,
        f"../textbook/pdf/{source_key}cc.jpg",
    )


def _extract_source_key(value: str) -> Optional[str]:
    """
    Extract NCERT's internal textbook key.

    Example:
        textbook.php?lhgy2=0-9 -> lhgy2
    """
    match = re.search(
        r"(?:^|/?)textbook\.php\?([^=&\s]+)",
        value,
        re.IGNORECASE,
    )
    return match.group(1).strip() if match else None


def _clean_raw_url(value: str) -> str:
    """
    Clean values copied from NCERT JavaScript.

    The live NCERT page normally contains plain URLs. This also tolerates
    Markdown-style URLs if a copied/debugged page happens to contain them.
    """
    value = value.strip()

    markdown = re.fullmatch(r"\[([^\]]+)\]\(([^)]+)\)", value)
    if markdown:
        value = markdown.group(2).strip()

    return value


def _legacy_source_key(
    raw_value: str,
    class_name: int,
    subject: str,
    title: str,
) -> str:
    """
    Create a deterministic ID for an active legacy/direct NCERT entry.

    We intentionally do not pretend this is an NCERT source key.
    """
    canonical = "|".join(
        [
            _clean_raw_url(raw_value).lower(),
            str(class_name),
            subject.lower(),
            title.lower(),
        ]
    )
    digest = hashlib.sha1(canonical.encode("utf-8")).hexdigest()[:12]
    return f"legacy-{digest}"


# ---------------------------------------------------------------------------
# Title / metadata parsing
# ---------------------------------------------------------------------------

def _parse_title_metadata(
    raw_title: str,
    subject_name: str,
) -> Tuple[str, str, str]:
    title = _normalize_text(raw_title)
    subject = _canonical_subject(subject_name)

    if not title:
        return "", "", subject

    language = ""

    for token in re.findall(r"\(([^()]+)\)", title):
        token = _normalize_text(token)

        if not token:
            continue

        language_value = _canonical_language(token)

        if language_value:
            language = language_value
            continue

        possible_subject = SUBJECT_ALIASES.get(token.lower())

        if possible_subject:
            subject = possible_subject

    return _remove_parenthetical(title), language, subject


# ---------------------------------------------------------------------------
# JavaScript extraction
# ---------------------------------------------------------------------------

def _extract_scripts(soup: BeautifulSoup) -> str:
    return "\n".join(
        script.string or script.get_text() or ""
        for script in soup.find_all("script")
    )


def _mask_javascript_comments(text: str) -> str:
    """
    Mask // and /* */ comments while preserving line structure.

    NCERT contains commented-out legacy textbook options. Those must NOT
    become BUDH records simply because our regex can see them.
    """
    chars = list(text)
    i = 0
    n = len(chars)
    in_string: Optional[str] = None
    escaped = False

    while i < n:
        ch = chars[i]
        nxt = chars[i + 1] if i + 1 < n else ""

        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == in_string:
                in_string = None

            i += 1
            continue

        if ch in {'"', "'", "`"}:
            in_string = ch
            i += 1
            continue

        if ch == "/" and nxt == "/":
            chars[i] = " "
            chars[i + 1] = " "
            i += 2

            while i < n and chars[i] not in "\r\n":
                chars[i] = " "
                i += 1

            continue

        if ch == "/" and nxt == "*":
            chars[i] = " "
            chars[i + 1] = " "
            i += 2

            while i < n:
                if chars[i] == "*" and i + 1 < n and chars[i + 1] == "/":
                    chars[i] = " "
                    chars[i + 1] = " "
                    i += 2
                    break

                if chars[i] not in "\r\n":
                    chars[i] = " "

                i += 1

            continue

        i += 1

    return "".join(chars)


def _extract_option_pairs(body: str) -> List[Tuple[int, str, str]]:
    """
    Extract active NCERT dropdown assignments as:

        (index, title, value)

    Commented-out options are removed before matching.
    """
    active = _mask_javascript_comments(body)

    text_pattern = re.compile(
        r'document\.test\.tbook\.options\[(\d+)\]\.text\s*=\s*"([^"]*)"',
        re.IGNORECASE,
    )

    value_pattern = re.compile(
        r'document\.test\.tbook\.options\[(\d+)\]\.value\s*=\s*"([^"]*)"',
        re.IGNORECASE,
    )

    texts = {
        int(index): _normalize_text(text)
        for index, text in text_pattern.findall(active)
    }

    values = {
        int(index): value.strip()
        for index, value in value_pattern.findall(active)
    }

    return [
        (index, texts.get(index, ""), values[index])
        for index in sorted(values)
        if values[index]
    ]


# ---------------------------------------------------------------------------
# NCERT class + subject block extraction
# ---------------------------------------------------------------------------

BLOCK_PATTERN = re.compile(
    r"""
    if\s*
    \(\s*
        \(\s*
            document\.test\.tclass\.value\s*==\s*(?P<class>\d+)
        \s*\)
        \s*&&\s*
        \(\s*
            document\.test\.tsubject\.options\[sind\]\.text\s*==\s*
            "(?P<subject>[^"]+)"
        \s*\)
    \s*\)\s*\{
        (?P<body>.*?)
    \}
    """,
    re.IGNORECASE | re.DOTALL | re.VERBOSE,
)


# ---------------------------------------------------------------------------
# Record construction
# ---------------------------------------------------------------------------

def _make_book(
    *,
    class_num: int,
    subject_name: str,
    raw_title: str,
    raw_value: str,
) -> Optional[Dict[str, object]]:
    raw_value = _clean_raw_url(raw_value)
    raw_title = _normalize_text(raw_title)

    if not raw_value or not raw_title:
        return None

    title, language, parsed_subject = _parse_title_metadata(
        raw_title,
        subject_name,
    )

    subject = parsed_subject or _canonical_subject(subject_name)

    if not subject:
        subject = "Unknown"

    source_key = _extract_source_key(raw_value)

    if source_key:
        book_id = f"ncert-{source_key}"
        source_type = "textbook"
        thumbnail = _build_thumbnail(source_key)
    else:
        legacy_id = _legacy_source_key(
            raw_value,
            class_num,
            subject,
            title,
        )

        book_id = f"ncert-{legacy_id}"
        source_key = ""
        source_type = "legacy"
        thumbnail = ""

    url = urljoin(NCERT_TEXTBOOK_URL, raw_value)

    return {
        "id": book_id,
        "title": title or subject,
        "class": class_num,
        "subject": subject,
        "language": language,
        "board": "NCERT",
        "provider": "NCERT",
        "publisher": "NCERT",
        "thumbnail": thumbnail,
        "url": url,
        "tags": _build_tags(
            title or subject,
            class_num,
            subject,
            language,
        ),
        "source": {
            "provider": "NCERT",
            "source_key": source_key,
            "source_type": source_type,
            "raw_title": raw_title,
            "raw_subject": subject_name,
            "raw_language": language,
            "raw_value": raw_value,
        },
    }


# ---------------------------------------------------------------------------
# Main provider
# ---------------------------------------------------------------------------

def get_books() -> List[Dict[str, object]]:
    """
    Fetch the official NCERT textbook catalogue and return metadata-only books.

    Rules:
      * Never download PDFs.
      * Use NCERT's source key whenever available.
      * Do not guess languages.
      * Ignore commented-out NCERT options.
      * Include active legacy/direct NCERT URLs without a textbook.php key.
      * Keep the raw NCERT value for auditing/debugging.
    """

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/151.0 Safari/537.36"
        ),
        "Accept": (
            "text/html,application/xhtml+xml,application/xml;"
            "q=0.9,*/*;q=0.8"
        ),
        "Accept-Language": "en-US,en;q=0.9",
        "Connection": "keep-alive",
    }

    session = requests.Session()

    retry_config = Retry(
        total=4,
        connect=4,
        read=4,
        backoff_factor=0.75,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset({"GET"}),
        raise_on_status=False,
    )

    session.mount(
        "https://",
        HTTPAdapter(max_retries=retry_config),
    )

    logger.info(
        "Fetching official NCERT catalogue: %s",
        NCERT_TEXTBOOK_URL,
    )

    try:
        response = session.get(
            NCERT_TEXTBOOK_URL,
            timeout=(10, 45),
            headers=headers,
        )

        response.raise_for_status()

    except requests.RequestException as exc:
        logger.error(
            "Failed to fetch NCERT catalogue: %s",
            exc,
        )
        return []

    logger.info(
        "NCERT response: HTTP %s",
        response.status_code,
    )

    logger.info(
        "NCERT content type: %s",
        response.headers.get("Content-Type", ""),
    )

    try:
        soup = BeautifulSoup(
            response.text,
            "html.parser",
        )

    except Exception as exc:
        logger.error(
            "Failed to parse NCERT HTML: %s",
            exc,
        )
        return []

    scripts = _extract_scripts(soup)

    logger.info(
        "NCERT HTML links found: %d",
        len(soup.select("a[href]")),
    )

    books: List[Dict[str, object]] = []
    seen_ids = set()

    blocks_found = 0
    options_found = 0
    legacy_count = 0
    skipped_empty = 0
    _active_map = {}

    # Parse class + subject blocks.
    #
    # The option helper removes JS comments before looking for assignments,
    # which means these are ignored:
    #
    # //document.test.tbook.options[3].text = "Old Book";
    # //document.test.tbook.options[3].value = "...";
    #
    # But this is retained:
    #
    # document.test.tbook.options[1].text = "Project Books";
    # document.test.tbook.options[1].value = "/book_publishing/...";
    #
    for match in BLOCK_PATTERN.finditer(scripts):
        blocks_found += 1

        class_num = int(match.group("class"))

        raw_subject_name = _normalize_text(
            match.group("subject")
        )

        subject_name = _canonical_subject(
            raw_subject_name
        )

        body = match.group("body")

        options = _extract_option_pairs(body)

        options_found += len(options)

        for _, raw_title, raw_value in options:
            if not raw_title or not raw_value:
                skipped_empty += 1
                continue

            book = _make_book(
                class_num=class_num,
                subject_name=subject_name,
                raw_title=raw_title,
                raw_value=raw_value,
            )

            if not book:
                skipped_empty += 1
                continue

            book_id = str(book["id"])

            # Record active evidence for this source_key so we can later
            # associate pm=="KEY" mappings and commented occurrences
            # with active options discovered in class/subject blocks.
            try:
                sk = book.get("source", {}).get("source_key")
            except Exception:
                sk = None

            if sk:
                # store first-seen strong evidence for this key
                if "_active_map" not in locals():
                    _active_map = {}

                if sk not in _active_map:
                    _active_map[sk] = {
                        "title": book.get("title"),
                        "class": book.get("class"),
                        "subject": book.get("subject"),
                        "raw_title": raw_title,
                        "raw_value": raw_value,
                    }

            if book_id in seen_ids:
                continue

            seen_ids.add(book_id)

            source = book.get("source", {})

            if source.get("source_type") == "legacy":
                legacy_count += 1

                logger.info(
                    "Included active NCERT legacy entry: "
                    "class=%s subject=%s title=%s url=%s",
                    class_num,
                    subject_name,
                    book["title"],
                    book["url"],
                )

            books.append(book)

    logger.info(
        "NCERT class/subject blocks found: %d",
        blocks_found,
    )

    logger.info(
        "NCERT active textbook options found: %d",
        options_found,
    )

    logger.info(
        "NCERT books extracted: %d",
        len(books),
    )

    logger.info(
        "NCERT active legacy/direct entries included: %d",
        legacy_count,
    )

    logger.info(
        "NCERT empty/invalid options skipped: %d",
        skipped_empty,
    )

    # -----------------------------------------------------------------------
    # Dynamic discovery of additional source keys and conservative legacy
    # candidate inclusion.
    # -----------------------------------------------------------------------
    # Extract pm=="KEY" title mappings (e.g., if(pm=="aeen1"){ document.write(...<strong>Marigold</strong>...) })
    pm_map: Dict[str, str] = {}

    for m in re.finditer(r'if\s*\(\s*pm\s*==\s*["\']([^"\']+)["\']\s*\)\s*\{(?P<body>.*?)\}', scripts, re.IGNORECASE | re.DOTALL):
        key = m.group(1).strip()
        body = m.group('body') or ""
        title = None

        sm = re.search(r'<strong>([^<]+)</strong>', body, re.IGNORECASE)
        if sm:
            title = _normalize_text(sm.group(1))
        else:
            dm = re.search(r'document\.write\(\s*["\'](?P<html>.*?)["\']\s*\)', body, re.IGNORECASE | re.DOTALL)
            if dm:
                inner = dm.group('html')
                sm2 = re.search(r'<strong>([^<]+)</strong>', inner, re.IGNORECASE)
                if sm2:
                    title = _normalize_text(sm2.group(1))

        if title:
            pm_map[key] = title

    # Find all textbook.php occurrences (including commented ones) and group by key
    occurrences: Dict[str, set] = {}

    for raw in re.findall(r'textbook\.php\?[^"\'\s]+', scripts, re.IGNORECASE):
        sk = _extract_source_key(raw)
        if not sk:
            continue
        occurrences.setdefault(sk, set()).add(raw)

    # For each discovered key not already present from active parsing, decide
    # whether to include it as a conservative legacy candidate.
    # Keys that must not be auto-included until explicitly verified.
    SKIP_KEYS = {"keep5", "lhlm3"}

    for key in sorted(occurrences.keys()):
        if key in SKIP_KEYS:
            continue
        book_id = f"ncert-{key}"
        if book_id in seen_ids:
            continue

        raw_values = sorted(occurrences[key])
        raw_value = raw_values[0]

        # Prefer titles discovered from active options; otherwise use pm=="KEY" mappings.
        title = None
        if key in _active_map:
            title = _active_map[key].get('title')

        if not title:
            title = pm_map.get(key)

        # If we have no reliable title evidence, skip this key.
        if not title:
            continue

        # Determine class/subject context from active evidence or by scanning
        # the class/subject blocks for occurrences of this raw_value.
        klass = None
        subject_name = ""

        if key in _active_map:
            klass = _active_map[key].get('class')
            subject_name = _active_map[key].get('subject') or ""
        else:
            for bm in BLOCK_PATTERN.finditer(scripts):
                body = bm.group('body') or ""
                if any(rv in body for rv in raw_values):
                    try:
                        klass = int(bm.group('class'))
                    except Exception:
                        klass = None

                    raw_subject_name = _normalize_text(bm.group('subject') or "")
                    subject_name = _canonical_subject(raw_subject_name)
                    break

        title_norm, language, parsed_subject = _parse_title_metadata(title, subject_name)
        subject_final = parsed_subject or _canonical_subject(subject_name)

        url = urljoin(NCERT_TEXTBOOK_URL, raw_value)

        legacy_book = {
            "id": book_id,
            "title": title_norm,
            "class": klass,
            "subject": subject_final,
            "language": language,
            "board": "NCERT",
            "provider": "NCERT",
            "publisher": "NCERT",
            "thumbnail": _build_thumbnail(key),
            "url": url,
            "tags": _build_tags(title_norm or key, klass, subject_final, language),
            "source": {
                "provider": "NCERT",
                "source_key": key,
                "source_type": "legacy",
                "raw_title": title,
                "raw_subject": subject_name,
                "raw_language": language,
                "raw_value": raw_value,
            },
        }

        seen_ids.add(book_id)
        books.append(legacy_book)
        legacy_count += 1


    # -----------------------------------------------------------------------
    # Conservative emergency fallback.
    # -----------------------------------------------------------------------

    if not books:
        logger.warning(
            "Structured NCERT parser returned zero records; "
            "attempting conservative source-key discovery."
        )

        clean_scripts = _mask_javascript_comments(
            scripts
        )

        discovered = sorted(
            set(
                re.findall(
                    r'textbook\.php\?[^"\s]+',
                    clean_scripts,
                    re.IGNORECASE,
                )
            )
        )

        for raw_value in discovered:
            source_key = _extract_source_key(
                raw_value
            )

            if not source_key:
                continue

            book_id = f"ncert-{source_key}"

            if book_id in seen_ids:
                continue

            seen_ids.add(book_id)

            url = urljoin(
                NCERT_TEXTBOOK_URL,
                raw_value,
            )

            books.append(
                {
                    "id": book_id,
                    "title": source_key,
                    "class": None,
                    "subject": "",
                    "language": "",
                    "board": "NCERT",
                    "provider": "NCERT",
                    "publisher": "NCERT",
                    "thumbnail": _build_thumbnail(
                        source_key
                    ),
                    "url": url,
                    "tags": _build_tags(
                        source_key,
                        None,
                        "",
                        "",
                    ),
                    "source": {
                        "provider": "NCERT",
                        "source_key": source_key,
                        "source_type": "textbook",
                        "raw_title": source_key,
                        "raw_subject": "",
                        "raw_language": "",
                        "raw_value": raw_value,
                    },
                }
            )

        logger.warning(
            "Emergency discovery found %d records.",
            len(books),
        )

    # -----------------------------------------------------------------------
    # Final deterministic ordering.
    # -----------------------------------------------------------------------

    books.sort(
        key=lambda book: (
            int(book["class"])
            if isinstance(book.get("class"), int)
            else 999,
            str(
                book.get("subject") or ""
            ).lower(),
            str(
                book.get("language") or ""
            ).lower(),
            str(
                book.get("title") or ""
            ).lower(),
            str(
                book.get("id") or ""
            ),
        )
    )

    # -----------------------------------------------------------------------
    # Diagnostics.
    # -----------------------------------------------------------------------

    known_languages = sorted(
        {
            str(book["language"])
            for book in books
            if book.get("language")
        }
    )

    unknown_language_count = sum(
        1
        for book in books
        if not book.get("language")
    )

    legacy_books = [
        book
        for book in books
        if book.get("source", {}).get(
            "source_type"
        ) == "legacy"
    ]

    logger.info(
        "Known languages detected: %s",
        (
            ", ".join(known_languages)
            if known_languages
            else "none"
        ),
    )

    logger.info(
        "Records with unknown/empty language: %d",
        unknown_language_count,
    )

    logger.info(
        "Final NCERT record count: %d",
        len(books),
    )

    if legacy_books:
        logger.info(
            "Active legacy/direct records:"
        )

        for book in legacy_books:
            logger.info(
                "  [%s] Class %s | %s | %s | %s",
                book["id"],
                book["class"],
                book["subject"],
                book["title"],
                book["url"],
            )

    if books:
        logger.info(
            "First 5 extracted records:"
        )

        for record in books[:5]:
            logger.info(
                "%s",
                record,
            )

    return books