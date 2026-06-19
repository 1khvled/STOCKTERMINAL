import sys
from pathlib import Path

p = Path('app/ai_engine.py')
text = p.read_text(encoding='utf-8')

# max_tokens adjustments
text = text.replace('max_tokens=2200', 'max_tokens=6000')
text = text.replace('"max_tokens": max_tokens or 2200', '"max_tokens": max_tokens or 6000')

text = text.replace('"max_tokens": max_tokens or 1200', '"max_tokens": max_tokens or 4000')
text = text.replace('messages, 1200, temp', 'messages, 4000, temp')

text = text.replace('max_tokens=600', 'max_tokens=2000')
text = text.replace('max_tokens=600)', 'max_tokens=2000)')

# prompt 1 modifications
text = text.replace('3-5 short sentences', '1-2 extensive paragraphs')
text = text.replace('2-4 sentences', '1-2 expansive paragraphs')
text = text.replace('1-3 sentences', '1-2 expansive paragraphs')
text = text.replace('3-5 sentences', '2-3 expansive paragraphs')
text = text.replace('no preamble, no markdown.', 'no preamble, no markdown. You must be highly expansive, verbose, and detailed in your analysis. Write extensively.')

# add verbosity rule to RULES blocks
text = text.replace('RULES:\n- Type:', 'RULES:\n- Verbosity: You are expected to write long, highly detailed, verbose paragraphs for all text fields. Do not hold back.\n- Type:')

# prompt 2 and 3 modifications
text = text.replace('Output ONLY the JSON below.', 'Output ONLY the JSON below. You must be highly expansive, verbose, and detailed. Write extensively.')
text = text.replace('Output ONLY the JSON below — no preamble.', 'Output ONLY the JSON below — no preamble. You must be highly expansive, verbose, and detailed. Write extensively.')

# chat prompt
text = text.replace('Answer in plain English, short sentences, and a calm confident tone. Be direct but not rude. Avoid jargon when possible.', "Answer in plain English, using highly expansive, verbose, and detailed paragraphs. Provide a comprehensive, in-depth explanation and 'yap' as much as possible.")
text = text.replace('You are StockerAI, a clear and practical stock analyst. Output plain text only. Be concise, helpful, and easy to understand.', 'You are StockerAI, a highly verbose and expansive stock analyst. Output plain text only. Write extensively and provide deeply detailed, comprehensive explanations. Do not hold back.')

p.write_text(text, encoding='utf-8')
print('Update complete.')
