import re

with open('app/static/js/dashboard.js', 'r', encoding='utf-8') as f:
    js = f.read()

with open('app/templates/dashboard.html', 'r', encoding='utf-8') as f:
    html = f.read()

matches = re.findall(r"document\.getElementById\(['\"]([^'\"]+)['\"]\)\.innerText\s*=", js)
for m in matches:
    if f'id="{m}"' not in html and f"id='{m}'" not in html:
        print('Missing HTML ID for innerText assignment:', m)

matches = re.findall(r"document\.getElementById\(['\"]([^'\"]+)['\"]\)\.innerHTML\s*=", js)
for m in matches:
    if f'id="{m}"' not in html and f"id='{m}'" not in html:
        print('Missing HTML ID for innerHTML assignment:', m)
