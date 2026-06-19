import re
from pathlib import Path

index_css_path = Path("app/static/css/index.css")

if index_css_path.exists():
    print("Modifying index.css...")
    with open(index_css_path, "r", encoding="utf-8") as f:
        content = f.read()

    # 1. Replace all box-shadow values with 'none'
    content = re.sub(r'box-shadow\s*:\s*[^;]+;', 'box-shadow: none;', content)

    # 2. Replace border-radius values with 0px (except dot grid background if any)
    content = re.sub(r'border-radius\s*:\s*(?!50%)[^;]+;', 'border-radius: 0px;', content)

    # 3. Strip text-shadows
    content = re.sub(r'text-shadow\s*:\s*[^;]+;', 'text-shadow: none;', content)

    # 4. Remove transitioning on shadows
    content = content.replace("box-shadow 0.3s ease", "border-color 0.3s ease")
    content = content.replace("box-shadow 0.25s", "border-color 0.25s")

    # 5. Clean up any glowing borders or indicators (remove blue border and replace with gray or red)
    # --emerald-glow, --emerald-border, etc.
    # We can replace them with flat colors
    content = content.replace("var(--emerald)", "#ffffff")
    content = content.replace("var(--emerald-border)", "#27272a")
    content = content.replace("var(--emerald-glow)", "#09090b")
    
    with open(index_css_path, "w", encoding="utf-8") as f:
        f.write(content)
    print("index.css updated.")
else:
    print("index.css not found.")
