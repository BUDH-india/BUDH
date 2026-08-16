from __future__ import annotations

import logging
import re
from typing import Dict, List, Optional
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


logger = logging.getLogger(__name__)

NCERT_TEXTBOOK_URL = "https://ncert.nic.in/textbook.php"


# ---------------------------------------------------------------------------
# NCERT CONTROLLED VOCABULARY
# ---------------------------------------------------------------------------

# These are languages that BUDH recognizes as actual language values.
# IMPORTANT:
# We do NOT infer a language merely because a word looks language-like.
#
# If NCERT gives a token that is not here, it remains unknown.
#
# This prevents things such as:
#   Bhugol     -> Geography
#   Itihas     -> History
#   EVS        -> Environmental Studies
#   Agriculture -> Agriculture
#
# from becoming languages.
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


# Things which can occur in parentheses but are subjects/categories,
# NOT languages.
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
# BASIC HELPERS
# ---------------------------------------------------------------------------

def _normalize_text(value: Optional[str]) -> str:
    """Normalize whitespace without changing the actual wording."""
    if not value:
        return ""

    return re.sub(r"\s+", " ", value).strip()


def _canonical_language(value: Optional[str]) -> str:
    """
    Convert a known language token to its canonical BUDH representation.

    Unknown values intentionally return "".

    We do NOT guess.
    """
    value = _normalize_text(value)

    if not value:
        return ""

    return LANGUAGE_MAP.get(value.lower(), "")


def _canonical_subject(value: Optional[str]) -> str:
    """
    Normalize a subject alias when it is explicitly recognizable.
    """
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
    """Build deterministic search tags."""

    tags: List[str] = []

    title_words = re.findall(r"[a-zA-Z0-9]+", title.lower())

    for word in title_words:
        if len(word) > 2 and word not in {
            "the",
            "for",
            "and",
            "with",
        }:
            tags.append(word)

    if class_name is not None:
        tags.append(f"class {class_name}")
        tags.append(f"grade {class_name}")

    if subject:
        tags.append(subject.lower())

    if language:
        tags.append(language.lower())

    tags.extend(
        [
            "ncert",
            "textbook",
        ]
    )

    return list(dict.fromkeys(tags))


def _extract_source_key(value: str) -> Optional[str]:
    """
    Extract NCERT's internal textbook key.

    Example:

        textbook.php?lhsk2=0-11

    ->

        lhsk2
    """

    match = re.search(
        r"textbook\.php\?([^=&\s]+)",
        value,
        re.IGNORECASE,
    )

    if not match:
        return None

    return match.group(1).strip()


def _build_thumbnail(source_key: Optional[str]) -> str:
    """Build NCERT's thumbnail URL from its internal textbook key."""

    if not source_key:
        return ""

    return urljoin(
        NCERT_TEXTBOOK_URL,
        f"../textbook/pdf/{source_key}cc.jpg",
    )


def _remove_parenthetical(value: str) -> str:
    """Remove one or more parenthetical annotations from a title."""

    value = re.sub(
        r"\s*\([^()]*\)\s*",
        " ",
        value,
    )

    return _normalize_text(value)


# ---------------------------------------------------------------------------
# LANGUAGE / TITLE PARSING
# ---------------------------------------------------------------------------

def _parse_title_metadata(
    raw_title: str,
    subject_name: str,
) -> tuple[str, str, str]:
    """
    Parse title, language and possible subject annotation.

    IMPORTANT:
    This function is deliberately conservative.

    Examples:

        "Math-Mela (English)"
            -> title = "Math-Mela"
            -> language = "English"

        "Sansadhan Avam Vikas (Bhugol)"
            -> title = "Sansadhan Avam Vikas"
            -> language = ""
            -> subject = "Geography"

        "Some Book (UnknownThing)"
            -> title = "Some Book"
            -> language = ""
            -> subject unchanged

    We never turn an unknown parenthetical token into a language.
    """

    title = _normalize_text(raw_title)
    subject = _canonical_subject(subject_name)

    if not title:
        return "", "", subject

    # Find parenthetical annotations.
    matches = re.findall(
        r"\(([^()]+)\)",
        title,
    )

    language = ""

    for raw_token in matches:
        token = _normalize_text(raw_token)

        if not token:
            continue

        canonical_language = _canonical_language(token)

        if canonical_language:
            language = canonical_language
            continue

        # It may explicitly identify a subject.
        possible_subject = SUBJECT_ALIASES.get(token.lower())

        if possible_subject:
            subject = possible_subject

    # Parenthetical annotations are metadata, not part of the title.
    clean_title = _remove_parenthetical(title)

    return clean_title, language, subject


# ---------------------------------------------------------------------------
# JAVASCRIPT EXTRACTION
# ---------------------------------------------------------------------------

def _extract_scripts(soup: BeautifulSoup) -> str:
    """Return all inline JavaScript from the NCERT catalogue."""

    return "\n".join(
        script.string or script.get_text() or ""
        for script in soup.find_all("script")
    )


def _extract_option_texts(body: str) -> Dict[int, str]:
    """Extract NCERT textbook dropdown option labels."""

    matches = re.findall(
        r'document\.test\.tbook\.options\[(\d+)\]\.text\s*=\s*"([^"]*)"',
        body,
    )

    return {
        int(index): _normalize_text(text)
        for index, text in matches
    }


def _extract_option_values(body: str) -> Dict[int, str]:
    """Extract NCERT textbook dropdown option URLs/values."""

    matches = re.findall(
        r'document\.test\.tbook\.options\[(\d+)\]\.value\s*=\s*"([^"]*)"',
        body,
    )

    return {
        int(index): value.strip()
        for index, value in matches
    }


# ---------------------------------------------------------------------------
# MAIN PARSER
# ---------------------------------------------------------------------------

def get_books() -> List[Dict[str, object]]:
    """
    Fetch the official NCERT textbook catalogue and return metadata-only
    records.

    Design principles:

    1. Never download PDFs.
    2. Never guess a language.
    3. Preserve NCERT's source key as the stable ID.
    4. Preserve unknown language as "".
    5. Keep provider-specific parsing inside this module.
    """

    headers = {
        "User-Agent": (
            "Mozilla/5.0 "
            "(Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 "
            "(KHTML, like Gecko) "
            "Chrome/151.0 Safari/537.36"
        )
    }

    session = requests.Session()

    retry_config = Retry(
        total=3,
        connect=3,
        read=3,
        backoff_factor=0.5,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset({"GET"}),
        raise_on_status=False,
    )

    session.mount(
        "https://",
        HTTPAdapter(
            max_retries=retry_config,
        ),
    )

    logger.info(
        "Fetching official NCERT catalogue: %s",
        NCERT_TEXTBOOK_URL,
    )

    try:
        response = session.get(
            NCERT_TEXTBOOK_URL,
            timeout=30,
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

    content_type = response.headers.get(
        "Content-Type",
        "",
    )

    logger.info(
        "NCERT content type: %s",
        content_type,
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

    all_links = soup.select("a[href]")

    logger.info(
        "NCERT HTML links found: %d",
        len(all_links),
    )

    # -----------------------------------------------------------------------
    # Find class + subject blocks.
    #
    # NCERT's catalogue JavaScript contains blocks similar to:
    #
    # if((document.test.tclass.value==12) &&
    #    (document.test.tsubject.options[sind].text=="Sanskrit")) {
    #
    #     document.test.tbook.options[...].text = "...";
    #     document.test.tbook.options[...].value = "...";
    # }
    # -----------------------------------------------------------------------

    block_pattern = re.compile(
        r"""
        if\s*
        \(\s*
        \(
            document\.test\.tclass\.value
            \s*==\s*
            (?P<class>\d+)
        \)
        \s*&&\s*
        \(
            document\.test\.tsubject\.options
            \[sind\]
            \.text
            \s*==\s*
            "(?P<subject>[^"]+)"
        \)
        \s*\)
        \s*\{
            (?P<body>.*?)
        \}
        """,
        re.IGNORECASE | re.DOTALL | re.VERBOSE,
    )

    books: List[Dict[str, object]] = []
    seen_ids = set()

    blocks_found = 0
    options_found = 0

    for match in block_pattern.finditer(scripts):

        blocks_found += 1

        class_num = int(
            match.group("class")
        )

        subject_name = _canonical_subject(
            match.group("subject")
        )

        body = match.group("body")

        option_texts = _extract_option_texts(
            body
        )

        option_values = _extract_option_values(
            body
        )

        options_found += len(option_values)

        for index, raw_value in option_values.items():

            if not raw_value:
                continue

            raw_title = option_texts.get(
                index,
                "",
            )

            if not raw_title:
                continue

            # ----------------------------------------------------------------
            # Parse metadata WITHOUT guessing.
            # ----------------------------------------------------------------

            title, language, parsed_subject = _parse_title_metadata(
                raw_title,
                subject_name,
            )

            subject = parsed_subject or subject_name

            # ----------------------------------------------------------------
            # Stable NCERT source identifier.
            # ----------------------------------------------------------------

            source_key = _extract_source_key(
                raw_value
            )

            if not source_key:
                logger.warning(
                    "Skipping NCERT option without source key: %s",
                    raw_value,
                )
                continue

            book_id = f"ncert-{source_key}"

            if book_id in seen_ids:
                continue

            seen_ids.add(book_id)

            # ----------------------------------------------------------------
            # Build official URLs.
            # ----------------------------------------------------------------

            url = urljoin(
                NCERT_TEXTBOOK_URL,
                raw_value,
            )

            thumbnail = _build_thumbnail(
                source_key
            )

            # ----------------------------------------------------------------
            # Record.
            # ----------------------------------------------------------------

            book: Dict[str, object] = {
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
                    "raw_title": raw_title,
                    "raw_subject": subject_name,
                    "raw_language": language,
                },
            }

            books.append(book)

    logger.info(
        "NCERT class/subject blocks found: %d",
        blocks_found,
    )

    logger.info(
        "NCERT textbook options found: %d",
        options_found,
    )

    logger.info(
        "NCERT books extracted: %d",
        len(books),
    )

    # -----------------------------------------------------------------------
    # Emergency fallback.
    #
    # This is intentionally conservative.
    #
    # We DO NOT invent class/subject/language metadata here.
    #
    # If NCERT changes its JavaScript structure, these records can be
    # investigated instead of silently producing fake metadata.
    # -----------------------------------------------------------------------

    if not books:

        logger.warning(
            "Structured NCERT parser returned zero records."
        )

        logger.warning(
            "Attempting metadata-only emergency discovery."
        )

        discovered = set(
            re.findall(
                r'textbook\.php\?[^"\s]+',
                scripts,
                re.IGNORECASE,
            )
        )

        for raw_value in sorted(discovered):

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
                        "raw_title": source_key,
                        "raw_subject": "",
                        "raw_language": "",
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

            str(book.get("subject") or "").lower(),

            str(book.get("language") or "").lower(),

            str(book.get("title") or "").lower(),

            str(book.get("id") or ""),
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

    logger.info(
        "Known languages detected: %s",
        ", ".join(known_languages)
        if known_languages
        else "none",
    )

    logger.info(
        "Records with unknown/empty language: %d",
        unknown_language_count,
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