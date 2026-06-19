# -*- coding: utf-8 -*-
import re
with open('app/static/js/dashboard.js', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace("el_pe_val.innerText = `${m.trailingPE || '—'} / ${m.forwardPE || '—'}`",
                          "el_pe_val.innerHTML = `${m.trailingPE || '—'} <span style=\\\"color:#c7c7cc;\\\">/</span> ${m.forwardPE || '—'}`")

content = content.replace("el_eps_val.innerText = `$${m.trailingEPS || '—'} / $${m.forwardEPS || '—'}`",
                          "el_eps_val.innerHTML = `$${m.trailingEPS || '—'} <span style=\\\"color:#c7c7cc;\\\">/</span> $${m.forwardEPS || '—'}`")

with open('app/static/js/dashboard.js', 'w', encoding='utf-8') as f:
    f.write(content)

print("Replaced successfully")
