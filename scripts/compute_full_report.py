import json
from urllib.parse import urlparse
from collections import Counter, defaultdict

before_path = 'data/books.before_parser_fix.json'
after_path = 'data/books.json'
out_path = 'scripts/full_parser_report.json'

with open(before_path, 'r', encoding='utf-8') as f:
    before_list = json.load(f)
with open(after_path, 'r', encoding='utf-8') as f:
    after_list = json.load(f)

before = {b['id']: b for b in before_list}
after = {b['id']: b for b in after_list}

# totals
before_total = len(before_list)
after_total = len(after_list)

# language changes (all records where language differs)
lang_changed = []
for idv,b in after.items():
    b0 = before.get(idv)
    if b0:
        l0 = (b0.get('language') or '').strip()
        l1 = (b.get('language') or '').strip()
        if l0 != l1:
            lang_changed.append({'id': idv, 'before': l0 or None, 'after': l1 or None, 'url': b.get('url')})

# 8 previously flagged records
flagged_ids = ['ncert-deap1','ncert-hhss4','ncert-hess4','ncert-hhss1','ncert-huug1','ncert-ieve1','ncert-ievw1','ncert-lhgy2']
flagged = []
for idv in flagged_ids:
    fa = after.get(idv)
    fb = before.get(idv)
    flagged.append({'id': idv, 'before': fb and fb.get('language'), 'after': fa and fa.get('language'), 'url': fa and fa.get('url')})

# derive allowed languages by frequency >=20 from parenthetical-derived language tokens approximation
# Approximate by language field counts in after_list
lang_counts = Counter([(b.get('language') or '').strip().lower() for b in after_list if (b.get('language') or '').strip()])
allowed_langs = [lang.title() for lang,count in lang_counts.items() if count >= 20]
allowed_langs_sorted = sorted(allowed_langs)

# records with empty/unknown language
empty_language = [ {'id':b['id'],'url':b.get('url')} for b in after_list if not (b.get('language') and str(b.get('language')).strip()) ]

# duplicates
ids = [b['id'] for b in after_list]
urls = [b.get('url') for b in after_list]
dup_ids = [k for k,v in Counter(ids).items() if v>1]
dup_urls = [k for k,v in Counter(urls).items() if v>1]

# missing titles/urls
missing_titles = [b['id'] for b in after_list if not b.get('title')]
missing_urls = [b['id'] for b in after_list if not b.get('url')]

# suspicious domains
suspicious = set()
for b in after_list:
    u = b.get('url')
    if not u:
        continue
    host = urlparse(u).netloc.lower()
    if host and not host.endswith('ncert.nic.in'):
        suspicious.add(host)

# class 13 and 14 records
class_13 = [b for b in after_list if b.get('class') == 13]
class_14 = [b for b in after_list if b.get('class') == 14]

# 10 representative records covering different classes/subjects/languages
seen = set()
representative = []
for b in after_list:
    key = (b.get('class'), b.get('subject'), (b.get('language') or '').lower())
    if key in seen:
        continue
    seen.add(key)
    representative.append({'id': b['id'], 'title': b.get('title'), 'class': b.get('class'), 'subject': b.get('subject'), 'language': b.get('language'), 'url': b.get('url')})
    if len(representative) >= 10:
        break

report = {
    'before_total': before_total,
    'after_total': after_total,
    'total_records_after': after_total,
    'language_changes_count': len(lang_changed),
    'language_changes': lang_changed,
    'flagged_records': flagged,
    'derived_allowed_languages': allowed_langs_sorted,
    'empty_language_records': empty_language,
    'duplicate_ids': dup_ids,
    'duplicate_urls': dup_urls,
    'missing_titles': missing_titles,
    'missing_urls': missing_urls,
    'suspicious_domains': sorted(list(suspicious)),
    'class_13_count': len(class_13),
    'class_13_records': class_13,
    'class_14_count': len(class_14),
    'class_14_records': class_14,
    'representative_samples': representative,
}

with open(out_path, 'w', encoding='utf-8') as f:
    json.dump(report, f, ensure_ascii=False, indent=2)

print('Wrote', out_path)
