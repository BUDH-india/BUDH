import json
from collections import Counter, defaultdict

with open('data/books.json', 'r', encoding='utf-8') as f:
    books = json.load(f)

classes = [b.get('class') for b in books if b.get('class') is not None]
langs = [ (b.get('class'), (b.get('language') or '').strip()) for b in books ]
subjects = [ (b.get('class'), (b.get('subject') or '').strip()) for b in books ]

class_counts = Counter(classes)
lang_counts = Counter([l for _, l in langs if l])
subject_counts = Counter([s for _, s in subjects if s])

# languages available per class
langs_per_class = defaultdict(set)
for c,l in langs:
    if l:
        langs_per_class[c].add(l)

# subjects per class (count)
subjects_per_class = defaultdict(Counter)
for c,s in subjects:
    if s:
        subjects_per_class[c][s] += 1

print(f"total_books: {len(books)}")
print(f"classes_covered_sorted: {sorted(set(classes))}")
print('class_counts:')
for c in sorted(class_counts):
    print(f"  class {c}: {class_counts[c]}")

print('\nlanguages_top:')
for l,count in lang_counts.most_common(20):
    print(f"  {l}: {count}")

print('\nlanguages_per_class_sample:')
for c in sorted(langs_per_class)[:12]:
    print(f"  class {c}: {sorted(langs_per_class[c])}")

print('\nunique_subjects_total:', len(subject_counts))
print('top_subjects:')
for s,count in subject_counts.most_common(20):
    print(f"  {s}: {count}")

# simple checks for missing classes 1..12
classes_present = set(classes)
missing_classes = [c for c in range(1,13) if c not in classes_present]
print('\nmissing_classes_1_12:', missing_classes)
