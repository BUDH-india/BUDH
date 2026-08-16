import json
import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse

IDS = [
    'ncert-deap1', 'ncert-hhss4', 'ncert-hess4', 'ncert-hhss1',
    'ncert-huug1', 'ncert-ieve1', 'ncert-ievw1', 'ncert-lhgy2'
]

with open('data/books.json','r',encoding='utf-8') as f:
    books = {b['id']: b for b in json.load(f)}

session = requests.Session()
session.headers.update({'User-Agent':'Mozilla/5.0 (investigator)'})

LANGUAGES = [
    'English','Hindi','Urdu','Assamese','Bengali','Bodo','Dogri','Gujarati','Kannada',
    'Kashmiri','Konkani','Maithili','Malayalam','Manipuri','Marathi','Nepali','Odia',
    'Punjabi','Sanskrit','Santhali','Sindhi','Tamil','Telugu'
]

results = []
for idv in IDS:
    rec = books.get(idv)
    if not rec:
        results.append({'id':idv,'error':'not in data/books.json'})
        continue
    url = rec.get('url')
    info = {'id':idv,'title':rec.get('title'),'class':rec.get('class'),'subject':rec.get('subject'),'language_field':rec.get('language'),'url':url,'http_status':None,'language_matches':[], 'snippets':[]}
    try:
        resp = session.get(url, timeout=15)
        info['http_status'] = resp.status_code
        text = resp.text
        soup = BeautifulSoup(text, 'html.parser')
        # search for explicit language words in page
        page_text = soup.get_text(separator='\n')
        found = set()
        snippets = []
        for lang in LANGUAGES:
            if re.search(rf"\b{re.escape(lang)}\b", page_text, re.I):
                found.add(lang)
                # capture a few lines with the match
                for line in page_text.splitlines():
                    if re.search(rf"\b{re.escape(lang)}\b", line, re.I):
                        snippets.append(line.strip())
                        if len(snippets)>=5:
                            break
        # also search for non-language tokens that caused flags
        extras = ['Bhugol','Itihas','EVS','Supl','Addawala','Agriculture']
        extra_found = []
        for e in extras:
            if re.search(rf"\b{re.escape(e)}\b", page_text, re.I):
                extra_found.append(e)
        info['language_matches'] = sorted(found)
        info['extras_found'] = extra_found
        info['snippets'] = snippets[:5]
    except Exception as exc:
        info['error'] = str(exc)
    results.append(info)

print(json.dumps(results, ensure_ascii=False, indent=2))
