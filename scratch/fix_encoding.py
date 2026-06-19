"""Fix emojis and encoding issues in benchmark_models.py"""
from pathlib import Path

p = Path('scratch/benchmark_models.py')
text = p.read_text(encoding='utf-8')

replacements = [
    ('\u2705', '[OK]'),
    ('\u274c', '[FAIL]'),
    ('\u26a0\ufe0f', '[WARN]'),
    ('\u26a0', '[WARN]'),
    ('\U0001f947', '[1]'),
    ('\U0001f948', '[2]'),
    ('\U0001f949', '[3]'),
    ('\U0001f3c6', '[WINNER]'),
    ('\u27a4', '->'),
    ('\U0001f3c1', ''),
    ('\u2014', '--'),
    ('\u2500', '-'),
    ('\u2502', '|'),
]
for old, new in replacements:
    text = text.replace(old, new)

header = 'import sys\nsys.stdout.reconfigure(encoding="utf-8", errors="replace")\n'
if 'sys.stdout.reconfigure' not in text:
    text = header + text

p.write_text(text, encoding='utf-8')
print('Fixed.')
