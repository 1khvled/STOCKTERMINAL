# -*- coding: utf-8 -*-
with open('app/static/js/dashboard.js', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace('"N/A"', '"—"').replace("'N/A'", "'—'")

with open('app/static/js/dashboard.js', 'w', encoding='utf-8') as f:
    f.write(content)

print("Replaced successfully")
