import json
with open('data/books.json','r',encoding='utf-8') as f:
    books = json.load(f)
langs = sorted({(b.get('language') or '').strip() for b in books if (b.get('language') or '').strip()})
print(len(langs))
for l in langs:
    print(l)
