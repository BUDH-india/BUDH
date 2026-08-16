import json
import random
import requests
from urllib.parse import urlparse
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

BOOKS_PATH = "data/books.json"
SAMPLE_SIZE = 20

with open(BOOKS_PATH, "r", encoding="utf-8") as f:
    books = json.load(f)

total = len(books)
print(f"total_books: {total}")

# duplicates across full dataset
ids = [b.get("id") for b in books]
urls = [b.get("url") for b in books]
dup_ids = {x for x in ids if ids.count(x) > 1}
dup_urls = {x for x in urls if urls.count(x) > 1}
print(f"duplicate_ids_total: {len(dup_ids)}")
print(f"duplicate_urls_total: {len(dup_urls)}")

# overall missing fields counts
missing_title = sum(1 for b in books if not b.get("title"))
missing_url = sum(1 for b in books if not b.get("url"))
print(f"missing_title_total: {missing_title}")
print(f"missing_url_total: {missing_url}")

# sample indices (deterministic)
random.seed(42)
indices = random.sample(range(total), min(SAMPLE_SIZE, total))

session = requests.Session()
retries = Retry(total=2, backoff_factor=0.3, status_forcelist=(500,502,503,504))
session.mount("https://", HTTPAdapter(max_retries=retries))
headers = {"User-Agent": "Mozilla/5.0 (validation-script)"}

sample_results = []

for i in indices:
    b = books[i]
    rec = {
        "index": i,
        "id": b.get("id"),
        "title": b.get("title"),
        "url": b.get("url"),
        "domain": None,
        "class": b.get("class"),
        "subject": b.get("subject"),
        "language": b.get("language"),
        "head_status": None,
        "method": None,
        "content_type": None,
        "error": None,
    }

    url = rec["url"]
    if not url:
        rec["error"] = "missing_url"
        sample_results.append(rec)
        continue

    parsed = urlparse(url)
    rec["domain"] = parsed.netloc.lower()

    # perform HEAD first
    try:
        resp = session.head(url, timeout=10, allow_redirects=True, headers=headers)
        rec["head_status"] = resp.status_code
        rec["method"] = "HEAD"
        rec["content_type"] = resp.headers.get("Content-Type")
        # treat 405 or 4xx/5xx as fallback to GET
        if resp.status_code == 405 or resp.status_code >= 400:
            raise requests.RequestException(f"HEAD not allowed or failed: {resp.status_code}")
    except requests.RequestException as exc:
        # try lightweight GET (stream, do not read body)
        try:
            resp = session.get(url, timeout=12, stream=True, allow_redirects=True, headers=headers)
            rec["head_status"] = resp.status_code
            rec["method"] = "GET"
            rec["content_type"] = resp.headers.get("Content-Type")
            # close without reading content
            resp.close()
        except Exception as exc2:
            rec["error"] = str(exc2)
    sample_results.append(rec)

# simple field sanity checks
malformed_class = []
malformed_subject = []
malformed_language = []
for b in books:
    c = b.get("class")
    if c is not None and not isinstance(c, int):
        malformed_class.append(b.get("id"))
    subj = b.get("subject")
    if subj is None or (isinstance(subj, str) and subj.strip() == ""):
        malformed_subject.append(b.get("id"))
    lang = b.get("language")
    if lang is not None and not isinstance(lang, str):
        malformed_language.append(b.get("id"))

print(f"malformed_class_total: {len(malformed_class)}")
print(f"malformed_subject_total: {len(malformed_subject)}")
print(f"malformed_language_total: {len(malformed_language)}")

# suspicious domains in full dataset (domains not ending with ncert.nic.in)
suspicious = set()
for u in urls:
    if not u:
        continue
    p = urlparse(u)
    host = p.netloc.lower()
    if host and not host.endswith("ncert.nic.in"):
        suspicious.add(host)

print(f"suspicious_domains_total: {len(suspicious)}")
if suspicious:
    print("suspicious_domains_sample:")
    for d in list(suspicious)[:10]:
        print(" -", d)

# display sample results
print('\nSAMPLE_RESULTS_START')
import pprint
pp = pprint.PrettyPrinter(indent=2)
for r in sample_results:
    pp.pprint(r)
print('SAMPLE_RESULTS_END')

# exit code 0
print('\nvalidation_done')
