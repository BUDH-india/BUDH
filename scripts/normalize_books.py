import json
import re
from collections import defaultdict

IN_PATH = 'data/books.json'
BACKUP_PATH = 'data/books.before_normalization.json'
REPORT_PATH = 'scripts/normalize_report.json'

with open(IN_PATH, 'r', encoding='utf-8') as f:
    books = json.load(f)

# write backup
with open(BACKUP_PATH, 'w', encoding='utf-8') as f:
    json.dump(books, f, ensure_ascii=False, indent=2)

# gather existing subjects to detect language values that are actually subjects
subjects_lower = { (b.get('subject') or '').strip().lower() for b in books }

# canonical language mapping (lowercase->canonical)
lang_map = {
    'english': 'English',
    'urdu': 'Urdu',
    'hindi': 'Hindi',
    'assamese': 'Assamese',
    'bengali': 'Bengali',
    'bangali': 'Bengali',
    'bodo': 'Bodo',
    'dogri': 'Dogri',
    'gujarati': 'Gujarati',
    'gujrati': 'Gujarati',
    'kannada': 'Kannada',
    'kashmiri': 'Kashmiri',
    'konkani': 'Konkani',
    'maithili': 'Maithili',
    'maithli': 'Maithili',
    'maithali': 'Maithili',
    'malayalam': 'Malayalam',
    'manipuri': 'Manipuri',
    'marathi': 'Marathi',
    'nepali': 'Nepali',
    'odia': 'Odia',
    'oriya': 'Odia',
    'punjabi': 'Punjabi',
    'sanskrit': 'Sanskrit',
    'santhali': 'Santhali',
    'sindhi': 'Sindhi',
    'tamil': 'Tamil',
    'telugu': 'Telugu',
    'kannada': 'Kannada',
    'bengali': 'Bengali',
}

# simple subject-normalization function: trim, collapse spaces, title case multiword
def normalize_subject(s):
    if s is None:
        return s
    s0 = s.strip()
    s0 = re.sub(r"\s+", ' ', s0)
    # preserve common uppercase acronyms like EVS
    if s0.upper() in ('EVS', 'ICT'):
        return s0.upper()
    # title case, but keep known words with specific casing
    return ' '.join([w.capitalize() for w in s0.split(' ')])

changed = []
review = []

normalized = []
class_counts = defaultdict(int)

for b in books:
    new_b = dict(b)
    rec_changed = False

    # language normalization
    orig_lang = (b.get('language') or '').strip()
    lang_lower = orig_lang.lower()
    new_lang = orig_lang
    lang_flag_review = False

    if orig_lang == '':
        # empty language -> leave and flag
        lang_flag_review = True
    elif lang_lower in lang_map:
        new_lang = lang_map[lang_lower]
        if new_lang != orig_lang:
            rec_changed = True
    else:
        # if language value matches a known subject, mark for review
        if lang_lower in subjects_lower:
            lang_flag_review = True
        else:
            # if language contains non-alpha or is unusually short, mark for review
            if not re.match(r'^[A-Za-z\- ]+$', orig_lang) or len(orig_lang) < 3:
                lang_flag_review = True
            else:
                # unknown but plausible language name - preserve original but mark for review
                lang_flag_review = True

    if not lang_flag_review:
        new_b['language'] = new_lang
    else:
        # preserve original value
        new_b['language'] = orig_lang

    # subject normalization
    orig_subj = b.get('subject')
    new_subj = normalize_subject(orig_subj) if orig_subj else orig_subj
    if new_subj != orig_subj:
        rec_changed = True
        new_b['subject'] = new_subj

    # class handling
    cls = b.get('class')
    if isinstance(cls, int):
        class_counts[cls] += 1
    else:
        # preserve as-is; no cast
        pass

    if rec_changed:
        changed.append({'id': b.get('id'), 'orig_language': orig_lang, 'new_language': new_b.get('language'), 'orig_subject': orig_subj, 'new_subject': new_b.get('subject')})

    if lang_flag_review:
        review.append({'id': b.get('id'), 'language': orig_lang, 'subject': b.get('subject'), 'title': b.get('title')})

    normalized.append(new_b)

# identify classes outside 1..12
out_of_range = [ { 'id': b.get('id'), 'class': b.get('class'), 'title': b.get('title'), 'subject': b.get('subject')} for b in normalized if isinstance(b.get('class'), int) and (b.get('class') <1 or b.get('class')>12) ]

# write normalized file (overwrite)
with open(IN_PATH, 'w', encoding='utf-8') as f:
    json.dump(normalized, f, ensure_ascii=False, indent=2)

report = {
    'total_records': len(books),
    'unique_languages_after_guessing': sorted(list({ (b.get('language') or '').strip() for b in normalized if (b.get('language') or '').strip() })),
    'unique_subjects_after': sorted(list({ (b.get('subject') or '').strip() for b in normalized if (b.get('subject') or '').strip() })),
    'records_per_class': { str(k): v for k,v in sorted(class_counts.items()) },
    'records_changed_count': len(changed),
    'records_changed_examples': changed[:10],
    'records_requiring_manual_review_count': len(review),
    'records_requiring_manual_review_examples': review[:20],
    'out_of_range_class_records': out_of_range,
}

with open(REPORT_PATH, 'w', encoding='utf-8') as f:
    json.dump(report, f, ensure_ascii=False, indent=2)

print('Normalization complete. Backup saved to', BACKUP_PATH)
print('Report written to', REPORT_PATH)
