# BUDH Metadata Pipeline

This repository now includes a metadata-only pipeline for generating a searchable NCERT textbook database.

## What it does

- Reads official NCERT textbook catalogue pages
- Extracts publicly available metadata only
- Never downloads PDFs or stores textbook contents
- Produces a normalized JSON file for BUDH search

## Files

- `providers/ncert.py` — NCERT provider implementation
- `scripts/update_books.py` — generation script
- `data/books.json` — generated metadata output

## Run

```bash
python scripts/update_books.py
```

## Notes

The provider architecture is intentionally modular so additional official providers can be added later without changing the update script.
