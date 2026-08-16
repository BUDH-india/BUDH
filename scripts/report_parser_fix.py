import json
from urllib.parse import urlparse
from collections import Counter

before_path = 'data/books.before_parser_fix.json'
after_path = 'data/books.json'

with open(before_path, 'r', encoding='utf-8') as f:
    before = {b['id']: b for b in json.load(f)}
with open(after_path, 'r', encoding='utf-8') as f:
    after_list = json.load(f)
    after = {b['id']: b for b in after_list}

total = len(after_list)

records_with_language = sum(1 for b in after_list if b.get('language'))
unique_languages = sorted({(b.get('language') or '').strip() for b in after_list if (b.get('language') or '').strip()})
unique_subjects = sorted({(b.get('subject') or '').strip() for b in after_list if (b.get('subject') or '').strip()})

# changes
changed = []
for idv,b in after.items():
    b0 = before.get(idv)
    if not b0:
        changed.append({'id': idv, 'reason': 'new_after'})
        continue
    diffs = {}
    for key in ('language','subject','class','title'):
        if b0.get(key) != b.get(key):
            diffs[key] = {'before': b0.get(key), 'after': b.get(key)}
    if diffs:
        changed.append({'id': idv, 'diffs': diffs})

# previously flagged records
flagged = ['ncert-deap1','ncert-hhss4','ncert-hess4','ncert-hhss1','ncert-huug1','ncert-ieve1','ncert-ievw1','ncert-lhgy2']
flagged_changes = []
for idv in flagged:
    fa = after.get(idv)
    fb = before.get(idv)
    flagged_changes.append({'id': idv, 'before': fb and fb.get('language'), 'after': fa and fa.get('language'), 'url': fa and fa.get('url')})

# duplicates
ids = [b['id'] for b in after_list]
urls = [b.get('url') for b in after_list]
dup_ids = [k for k,v in Counter(ids).items() if v>1]
dup_urls = [k for k,v in Counter(urls).items() if v>1]

# missing
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

# malformed fields
malformed_class = [b['id'] for b in after_list if b.get('class') is not None and not isinstance(b.get('class'), int)]
malformed_subject = [b['id'] for b in after_list if not b.get('subject')]
malformed_language = [b['id'] for b in after_list if b.get('language') and not isinstance(b.get('language'), str)]

# sample 10 representative records
sample_ids = [
    'ncert-aejm1','ncert-ahjm1','ncert-auri1','ncert-deap1','ncert-hhss4','ncert-hhss1','ncert-huug1','ncert-ieve1','ncert-ievw1','ncert-lhgy2'
]
samples = [after.get(i) for i in sample_ids if after.get(i)]

report = {
    'total_records': total,
    'records_with_language': records_with_language,
    'unique_languages': unique_languages,
    'unique_subjects': unique_subjects,
    'records_changed_count': len(changed),
    'records_changed_examples': changed[:20],
    'flagged_records': flagged_changes,
    'duplicate_ids': dup_ids,
    'duplicate_urls': dup_urls,
    'missing_titles': missing_titles,
    'missing_urls': missing_urls,
    'suspicious_domains': list(suspicious),
    'malformed_class_count': len(malformed_class),
    'malformed_subject_count': len(malformed_subject),
    'malformed_language_count': len(malformed_language),
    'representative_samples': samples,
}

print(json.dumps(report, ensure_ascii=False, indent=2))
