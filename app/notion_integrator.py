"""
Notion Integrator -- Fetches, parses, and formats company qualitative research notes
from the user's Notion board to embed into the Quant Terminal HTML Dashboard.
"""
import requests
import json
import logging
from config import NOTION_TOKEN, NOTION_PAGE_ID

logger = logging.getLogger("notion_integrator")

HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Notion-Version": "2022-06-28",
    "Content-Type": "application/json"
}

def get_block_children(block_id):
    """Fetch all children blocks of a given Notion block with pagination."""
    url = f"https://api.notion.com/v1/blocks/{block_id}/children"
    results = []
    has_more = True
    next_cursor = None
    
    while has_more:
        params = {}
        if next_cursor:
            params["start_cursor"] = next_cursor
        
        try:
            response = requests.get(url, headers=HEADERS, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if "results" not in data:
                logger.error(f"Error retrieving children for block {block_id}: {data}")
                break
                
            results.extend(data["results"])
            has_more = data.get("has_more", False)
            next_cursor = data.get("next_cursor")
        except Exception as e:
            logger.error(f"HTTP request failed for block {block_id} children: {e}")
            break
            
    return results

def blocks_to_html(blocks):
    """Parse Notion block list and convert it into high-end styled HTML recursively."""
    html_parts = []
    in_bullet_list = False
    in_numbered_list = False
    
    for block in blocks:
        block_type = block.get("type")
        
        # Close open list tags if block type shifts
        if block_type != "bulleted_list_item" and in_bullet_list:
            html_parts.append("</ul>")
            in_bullet_list = False
        if block_type != "numbered_list_item" and in_numbered_list:
            html_parts.append("</ol>")
            in_numbered_list = False
            
        if block_type == "paragraph":
            text_objs = block.get("paragraph", {}).get("rich_text", [])
            text = "".join([t.get("plain_text", "") for t in text_objs])
            child_html = ""
            if block.get("has_children", False):
                children = get_block_children(block["id"])
                child_html = f'<div class="notion-indented">{blocks_to_html(children)}</div>'
                
            if text.strip():
                escaped_text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                html_parts.append(f'<p class="notion-p">{escaped_text}{child_html}</p>')
            elif child_html:
                html_parts.append(child_html)
            else:
                html_parts.append('<div class="notion-spacer"></div>')
                
        elif block_type == "heading_1":
            text_objs = block.get("heading_1", {}).get("rich_text", [])
            text = "".join([t.get("plain_text", "") for t in text_objs])
            escaped_text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            html_parts.append(f'<h1 class="notion-h1">{escaped_text}</h1>')
            
        elif block_type == "heading_2":
            text_objs = block.get("heading_2", {}).get("rich_text", [])
            text = "".join([t.get("plain_text", "") for t in text_objs])
            escaped_text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            html_parts.append(f'<h2 class="notion-h2">{escaped_text}</h2>')
            
        elif block_type == "heading_3":
            text_objs = block.get("heading_3", {}).get("rich_text", [])
            text = "".join([t.get("plain_text", "") for t in text_objs])
            escaped_text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            html_parts.append(f'<h3 class="notion-h3">{escaped_text}</h3>')
            
        elif block_type == "bulleted_list_item":
            if not in_bullet_list:
                html_parts.append('<ul class="notion-ul">')
                in_bullet_list = True
            text_objs = block.get("bulleted_list_item", {}).get("rich_text", [])
            text = "".join([t.get("plain_text", "") for t in text_objs])
            escaped_text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            child_html = ""
            if block.get("has_children", False):
                children = get_block_children(block["id"])
                child_html = blocks_to_html(children)
            html_parts.append(f'<li>{escaped_text}{child_html}</li>')
            
        elif block_type == "numbered_list_item":
            if not in_numbered_list:
                html_parts.append('<ol class="notion-ol">')
                in_numbered_list = True
            text_objs = block.get("numbered_list_item", {}).get("rich_text", [])
            text = "".join([t.get("plain_text", "") for t in text_objs])
            escaped_text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            child_html = ""
            if block.get("has_children", False):
                children = get_block_children(block["id"])
                child_html = blocks_to_html(children)
            html_parts.append(f'<li>{escaped_text}{child_html}</li>')
            
        elif block_type == "quote":
            text_objs = block.get("quote", {}).get("rich_text", [])
            text = "".join([t.get("plain_text", "") for t in text_objs])
            escaped_text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            child_html = ""
            if block.get("has_children", False):
                children = get_block_children(block["id"])
                child_html = f'<div class="notion-indented">{blocks_to_html(children)}</div>'
            html_parts.append(f'<blockquote class="notion-quote">{escaped_text}{child_html}</blockquote>')
            
        elif block_type == "table":
            table_id = block["id"]
            rows = get_block_children(table_id)
            if rows:
                html_parts.append('<div class="table-container" style="margin: 14px 0;"><table class="statement-table">')
                for idx, row in enumerate(rows):
                    cells = row.get("table_row", {}).get("cells", [])
                    html_parts.append('<tr>')
                    for cell in cells:
                        cell_text = "".join([t.get("plain_text", "") for t in cell])
                        escaped_text = cell_text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                        if idx == 0:
                            html_parts.append(f'<th>{escaped_text}</th>')
                        else:
                            html_parts.append(f'<td>{escaped_text}</td>')
                    html_parts.append('</tr>')
                html_parts.append('</table></div>')
                
        elif block_type == "column_list":
            cols = get_block_children(block["id"])
            for col in cols:
                col_children = get_block_children(col["id"])
                html_parts.append(blocks_to_html(col_children))
 
        elif block_type == "callout":
            text_objs = block.get("callout", {}).get("rich_text", [])
            text = "".join([t.get("plain_text", "") for t in text_objs])
            escaped_text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            child_html = ""
            if block.get("has_children", False):
                children = get_block_children(block["id"])
                child_html = blocks_to_html(children)
            html_parts.append(f'<div class="notion-callout"><div class="notion-callout-text">{escaped_text}</div>{child_html}</div>')
 
        elif block_type == "toggle":
            text_objs = block.get("toggle", {}).get("rich_text", [])
            text = "".join([t.get("plain_text", "") for t in text_objs])
            escaped_text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            child_html = ""
            if block.get("has_children", False):
                children = get_block_children(block["id"])
                child_html = blocks_to_html(children)
            html_parts.append(f'<details class="notion-details"><summary>{escaped_text}</summary><div class="notion-details-content">{child_html}</div></details>')
 
        elif block_type == "to_do":
            text_objs = block.get("to_do", {}).get("rich_text", [])
            text = "".join([t.get("plain_text", "") for t in text_objs])
            checked = block.get("to_do", {}).get("checked", False)
            escaped_text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            checkbox = '<input type="checkbox" checked disabled>' if checked else '<input type="checkbox" disabled>'
            html_parts.append(f'<div class="notion-todo">{checkbox} <span>{escaped_text}</span></div>')
 
        elif block_type == "code":
            text_objs = block.get("code", {}).get("rich_text", [])
            text = "".join([t.get("plain_text", "") for t in text_objs])
            escaped_text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            lang = block.get("code", {}).get("language", "plaintext")
            html_parts.append(f'<pre class="notion-code"><code class="language-{lang}">{escaped_text}</code></pre>')
 
        elif block_type == "divider":
            html_parts.append('<hr class="notion-hr" />')
 
        elif block_type == "synced_block":
            if block.get("has_children", False):
                children = get_block_children(block["id"])
                synced_html = blocks_to_html(children)
                html_parts.append(synced_html)
                
        elif block_type == "image":
            image_obj = block.get("image", {})
            img_type = image_obj.get("type")
            img_url = ""
            if img_type == "external":
                img_url = image_obj.get("external", {}).get("url", "")
            elif img_type == "file":
                img_url = image_obj.get("file", {}).get("url", "")
                
            caption_objs = image_obj.get("caption", [])
            caption_text = "".join([t.get("plain_text", "") for t in caption_objs])
            
            if img_url:
                caption_html = f'<div class="notion-img-caption">{caption_text}</div>' if caption_text else ''
                html_parts.append(f'<div class="notion-img-container"><img src="{img_url}" class="notion-img" alt="Notion Qualitative Asset" />{caption_html}</div>')
                
    # Close lists if they were still open at the end
    if in_bullet_list:
        html_parts.append("</ul>")
    if in_numbered_list:
        html_parts.append("</ol>")
        
    return "\n".join(html_parts)

def fetch_notion_data(ticker):
    """
    Search the main page for a child page matching the ticker,
    then fetch and parse all direct notes (Overview) and subpages recursively.
    """
    if not NOTION_TOKEN or not NOTION_PAGE_ID:
        logger.info("Notion credentials not fully configured in environment. Skipping Notion integration.")
        return None
        
    ticker_upper = ticker.strip().upper()
    logger.info(f"Connecting to Notion to look for ticker: {ticker_upper}...")
    
    # 1. Fetch children of the root dashboard page
    root_blocks = get_block_children(NOTION_PAGE_ID)
    company_page_id = None
    matched_title = None
    
    for block in root_blocks:
        if block.get("type") == "child_page":
            title = block.get("child_page", {}).get("title", "")
            title_upper = title.upper()
            
            # Match titles like "MU — Micron Technology Inc." or "AAPL — Apple Inc."
            if title_upper.startswith(ticker_upper + " ") or title_upper.startswith(ticker_upper + "—") or title_upper.startswith(ticker_upper + " -") or title_upper == ticker_upper:
                company_page_id = block["id"]
                matched_title = title
                break
                
    if not company_page_id:
        # Secondary fallback: check if ticker is a standalone word in the title
        for block in root_blocks:
            if block.get("type") == "child_page":
                title = block.get("child_page", {}).get("title", "")
                words = [w.strip("—-,. ") for w in title.upper().split()]
                if ticker_upper in words:
                    company_page_id = block["id"]
                    matched_title = title
                    break
                    
    if not company_page_id:
        logger.info(f"No matching Notion company page found for ticker '{ticker_upper}'. Initiating dynamic AI auto-generation...")
        company_page_id = auto_generate_notion_page(ticker_upper)
        if company_page_id:
            # Re-fetch root blocks to find the newly created page
            root_blocks = get_block_children(NOTION_PAGE_ID)
            for block in root_blocks:
                if block.get("type") == "child_page":
                    title = block.get("child_page", {}).get("title", "")
                    if title.upper().startswith(ticker_upper):
                        company_page_id = block["id"]
                        matched_title = title
                        break
        
    if not company_page_id:
        logger.info(f"No matching Notion company page found for ticker '{ticker_upper}' (auto-generation skipped/failed).")
        return None
        
    logger.info(f"📡 Linked to Notion company hub page: '{matched_title}' (ID: {company_page_id})")
    
    # 2. Fetch blocks directly on the company page
    company_blocks = get_block_children(company_page_id)
    subpages_data = {}
    overview_blocks = []
    
    for block in company_blocks:
        if block.get("type") == "child_page":
            sub_title = block.get("child_page", {}).get("title", "")
            sub_page_id = block["id"]
            
            logger.info(f"Fetching subpage content: '{sub_title}'...")
            subpage_blocks = get_block_children(sub_page_id)
            subpage_html = blocks_to_html(subpage_blocks)
            
            # Map normalized clean key names
            norm_key = sub_title.lower().replace(" ", "_")
            key_name = norm_key
            if "briefing" in norm_key:
                key_name = "briefing"
            elif "price" in norm_key or "review" in norm_key:
                key_name = "price_review"
            elif "risk" in norm_key:
                key_name = "risks"
            elif "earnings" in norm_key:
                key_name = "earnings"
                
            subpages_data[key_name] = {
                "title": sub_title,
                "html": subpage_html
            }
        else:
            overview_blocks.append(block)
            
    if overview_blocks:
        overview_html = blocks_to_html(overview_blocks)
        if overview_html.strip():
            subpages_data["overview"] = {
                "title": "Overview",
                "html": overview_html
            }
            logger.info("Compiled direct parent page blocks under 'Overview' tab.")
                
    return {
        "company_title": matched_title,
        "page_id": company_page_id,
        "subpages": subpages_data
    }

def auto_generate_notion_page(ticker):
    """
    Query the active AI model to generate comprehensive qualitative research,
    then automatically create and populate pages in the user's Notion board.
    """
    import yfinance as yf
    import re
    from ai_engine import _call_llm
    
    print(f"\n[!] Notion page for '{ticker}' not found. Automatically drafting qualitative research via AI...")
    
    # Get company name dynamically
    company_name = f"{ticker} Corp"
    try:
        ticker_obj = yf.Ticker(ticker)
        info = ticker_obj.info
        company_name = info.get("longName") or info.get("shortName") or f"{ticker} Corp"
    except Exception:
        pass
        
    system_prompt = "You are an elite equity research analyst. Generate institutional-grade qualitative research in JSON format."
    user_prompt = f"""Generate a comprehensive qualitative research dataset for '{ticker} — {company_name}' in raw JSON.
    
    Your output MUST be a JSON object with exactly these 5 keys, and all values MUST be highly detailed, comprehensive multi-paragraph Markdown:
    {{
      "overview": "Overview of {company_name} NYSE:{ticker}. Include key metrics like business category, headquarters, and founder overview.",
      "briefing": "## What They Do\\nDetailed business operations and value proposition...\\n\\n## Business Segments\\n| Segment | Revenue | YoY% | Notes |\\n| Segment 1 | $X | +Y% | Detail |\\n\\n## Competitive Moat\\nDetail brand, switching costs, cost advantages...\\n\\n## Key Leadership\\n| Role | Name | Notes |\\n| CEO | Name | Detail |",
      "price_review": "## Recent Financial Performance\\nKey quarterly earnings summary and surprises...\\n\\n## Valuation Snapshot\\n| Multiple | Value | Target/Consensus |\\n| P/E TTM | X | Y |\\n\\n## Secular Catalysts\\n- Catalyst 1 with detail\\n- Catalyst 2 with detail",
      "risks": "## Risk Overview\\nDetail structural or industry challenges...\\n\\n## Risk Register\\n1. Risk 1: Operational failure or market slowing risk with detailed mechanism.\\n2. Risk 2: High-density competitive threat detail.",
      "earnings": "## Earnings Call Review\\nKey details of recent quarterly guidance and surprise rates...\\n\\n## Recent Results\\n| Metric | Actual | Estimate | Beat/Miss |\\n| Revenue | $X | $Y | Z% |"
    }}
    
    Format everything in clean Markdown (using H2 '##', H3 '###', tables, bullet lists, numbered lists, dividers '---'). Do NOT return safety warnings, apologies, or disclaimers."""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]
    
    # Retrieve qualitative draft
    res_json = _call_llm(messages, max_tokens=3000, system_prompt=system_prompt)
    if not res_json or not isinstance(res_json, dict):
        print(f"  [-] Failed to generate AI qualitative research for '{ticker}'. Skipping Notion page creation.")
        return None
        
    print(f"  [+] Drafted premium qualitative reports for '{ticker}'. Injecting into Notion workspace...")
    
    # Notion API Header
    HEADERS = {
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json"
    }
    
    try:
        # Step 1: Create Parent Ticker Page
        parent_payload = {
            "parent": {"page_id": NOTION_PAGE_ID},
            "properties": {
                "title": {
                    "title": [{"text": {"content": f"{ticker} — {company_name}"}}]
                }
            }
        }
        resp = requests.post("https://api.notion.com/v1/pages", headers=HEADERS, json=parent_payload, timeout=20)
        resp.raise_for_status()
        parent_id = resp.json()["id"]
        print(f"  [+] Created main Notion page for '{ticker}' (ID: {parent_id})")
        
        # Step 1b: Populate Overview on Parent Page
        overview_md = res_json.get("overview", "")
        if overview_md:
            overview_blocks = markdown_to_notion_blocks(overview_md)
            if overview_blocks:
                requests.patch(f"https://api.notion.com/v1/blocks/{parent_id}/children", headers=HEADERS, json={"children": overview_blocks}, timeout=15)
                
        # Step 2: Create Subpages
        subpages_to_create = [
            ("📋 Company Briefing", res_json.get("briefing", "")),
            ("📈 Stock Price Review", res_json.get("price_review", "")),
            ("⚠️ Risks", res_json.get("risks", "")),
            ("💰 Earnings", res_json.get("earnings", ""))
        ]
        
        for title, md in subpages_to_create:
            if not md:
                continue
            blocks = markdown_to_notion_blocks(md)
            subpage_payload = {
                "parent": {"page_id": parent_id},
                "properties": {
                    "title": {
                        "title": [{"text": {"content": title}}]
                    }
                },
                "children": blocks[:100]  # Notion allows max 100 children in single page creation
            }
            sub_resp = requests.post("https://api.notion.com/v1/pages", headers=HEADERS, json=subpage_payload, timeout=20)
            sub_resp.raise_for_status()
            print(f"    -> Created subpage: '{title}'")
            
        print(f"  [+] Fully populated Notion qualitative workspace for '{ticker}' successfully!")
        return parent_id
        
    except Exception as e:
        print(f"  [-] Failed to write qualitative research to Notion API: {e}")
        print("  [!] Please ensure your Notion parent page is shared with the integration token.")
        return None

def markdown_to_notion_blocks(markdown_text):
    """Parse raw Markdown strings and map them recursively to native Notion block structures."""
    import re
    blocks = []
    lines = [line.strip() for line in markdown_text.split("\n")]
    
    in_table = False
    table_rows = []
    
    for line in lines:
        if not line:
            if in_table and table_rows:
                blocks.append(build_notion_table_block(table_rows))
                in_table = False
                table_rows = []
            continue
            
        # Parse table row
        if line.startswith("|") and line.endswith("|"):
            if "---" in line:
                continue
            in_table = True
            cells = [cell.strip() for cell in line.split("|")[1:-1]]
            table_rows.append(cells)
            continue
        elif in_table:
            if table_rows:
                blocks.append(build_notion_table_block(table_rows))
            in_table = False
            table_rows = []
            
        if line.startswith("## "):
            content = line[3:].strip()
            blocks.append({
                "object": "block",
                "type": "heading_2",
                "heading_2": {
                    "rich_text": [{"type": "text", "text": {"content": content}}]
                }
            })
        elif line.startswith("### "):
            content = line[4:].strip()
            blocks.append({
                "object": "block",
                "type": "heading_3",
                "heading_3": {
                    "rich_text": [{"type": "text", "text": {"content": content}}]
                }
            })
        elif line.startswith("- ") or line.startswith("* "):
            content = line[2:].strip()
            blocks.append({
                "object": "block",
                "type": "bulleted_list_item",
                "bulleted_list_item": {
                    "rich_text": [{"type": "text", "text": {"content": content}}]
                }
            })
        elif re.match(r'^\d+\.\s', line):
            content = re.sub(r'^\d+\.\s', '', line).strip()
            blocks.append({
                "object": "block",
                "type": "numbered_list_item",
                "numbered_list_item": {
                    "rich_text": [{"type": "text", "text": {"content": content}}]
                }
            })
        elif line.startswith("> "):
            content = line[2:].strip()
            blocks.append({
                "object": "block",
                "type": "quote",
                "quote": {
                    "rich_text": [{"type": "text", "text": {"content": content}}]
                }
            })
        elif line == "---":
            blocks.append({
                "object": "block",
                "type": "divider",
                "divider": {}
            })
        else:
            blocks.append({
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [{"type": "text", "text": {"content": line}}]
                }
            })
            
    if in_table and table_rows:
        blocks.append(build_notion_table_block(table_rows))
        
    return blocks

def build_notion_table_block(rows):
    """Build a native Notion table block child from rows."""
    width = len(rows[0])
    children = []
    for r in rows:
        cells = []
        for cell in r:
            cells.append([{"type": "text", "text": {"content": cell}}])
        children.append({
            "object": "block",
            "type": "table_row",
            "table_row": {"cells": cells}
        })
    return {
        "object": "block",
        "type": "table",
        "table": {
            "table_width": width,
            "has_column_header": True,
            "has_row_header": False
        },
        "children": children
    }
