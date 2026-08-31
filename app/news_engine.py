import os
import time
import requests
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
import yfinance as yf
from datetime import datetime, timedelta
import concurrent.futures

NEWS_CACHE = {}
CORP_NEWS_CACHE = {}
CACHE_TTL = 600  # 10 minutes

from dotenv import load_dotenv
load_dotenv()

def get_finnhub_key():
    return os.environ.get("FINNHUB_API_KEY")

def get_alphavantage_key():
    return os.environ.get("ALPHAVANTAGE_API_KEY")

def fetch_google_news(ticker, short_name):
    query = f"{ticker} stock OR {short_name}" if short_name else f"{ticker} stock"
    url = f"https://news.google.com/rss/search?q={urllib.parse.quote(query)}&hl=en-US&gl=US&ceid=US:en"
    news = []
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=5) as response:
            tree = ET.parse(response)
            root = tree.getroot()
            count = 0
            for item in root.findall('./channel/item'):
                if count >= 4: break
                title = item.find('title').text if item.find('title') is not None else "News"
                link = item.find('link').text if item.find('link') is not None else "#"
                source = item.find('source').text if item.find('source') is not None else "Google News"
                pubDate = item.find('pubDate').text if item.find('pubDate') is not None else ""
                news.append({
                    "title": title,
                    "link": link,
                    "publisher": f"Google News ({source})",
                    "pubDate": pubDate
                })
                count += 1
    except Exception as e:
        print(f"Google News error: {e}")
    return news

def fetch_duckduckgo_news(ticker, short_name):
    news = []
    query = f"{ticker} stock OR {short_name}" if short_name else f"{ticker} stock"
    try:
        from duckduckgo_search import DDGS
        with DDGS() as ddgs:
            results = ddgs.news(query, max_results=4)
            for r in results:
                news.append({
                    "title": r.get('title', "News"),
                    "link": r.get('url', "#"),
                    "publisher": f"DuckDuckGo ({r.get('source', 'Web')})",
                    "pubDate": r.get('date', "")
                })
    except Exception as e:
        print(f"DuckDuckGo error: {e}")
    return news

def fetch_finnhub_news(ticker):
    news = []
    api_key = get_finnhub_key()
    if not api_key: return news
    try:
        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
        url = f"https://finnhub.io/api/v1/company-news?symbol={ticker}&from={start_date}&to={end_date}&token={api_key}"
        res = requests.get(url, timeout=5)
        if res.status_code == 200:
            data = res.json()
            if isinstance(data, list):
                for n in data[:4]:
                    ts = n.get('datetime')
                    pubDate = datetime.fromtimestamp(ts).strftime("%a, %d %b %Y %H:%M:%S GMT") if ts else ""
                    news.append({
                        "title": n.get('headline', "News"),
                        "link": n.get('url', "#"),
                        "publisher": f"Finnhub ({n.get('source', 'Web')})",
                        "pubDate": pubDate
                    })
    except Exception as e:
        print(f"Finnhub error: {e}")
    return news

def fetch_alphavantage_news(ticker):
    news = []
    api_key = get_alphavantage_key()
    if not api_key: return news
    try:
        url = f"https://www.alphavantage.co/query?function=NEWS_SENTIMENT&tickers={ticker}&limit=4&apikey={api_key}"
        res = requests.get(url, timeout=5)
        if res.status_code == 200:
            data = res.json()
            if 'feed' in data:
                for n in data['feed'][:4]:
                    time_published = n.get('time_published', "")
                    pubDate = ""
                    if time_published and len(time_published) >= 15:
                        try:
                            dt = datetime.strptime(time_published[:15], "%Y%m%dT%H%M%S")
                            pubDate = dt.strftime("%a, %d %b %Y %H:%M:%S GMT")
                        except: pass
                    news.append({
                        "title": n.get('title', "News"),
                        "link": n.get('url', "#"),
                        "publisher": f"Alpha Vantage ({n.get('source', 'Web')})",
                        "pubDate": pubDate
                    })
    except Exception as e:
        print(f"Alpha Vantage error: {e}")
    return news

def parse_date(date_str):
    if not date_str: return datetime.min
    try:
        # Handle standard RFC 2822
        return datetime.strptime(date_str[:25].strip(), "%a, %d %b %Y %H:%M:%S").replace(tzinfo=None)
    except:
        try:
            # Handle DDG ISO
            return datetime.fromisoformat(date_str.replace("Z", "+00:00")).replace(tzinfo=None)
        except:
            return datetime.min

def get_aggregated_news(ticker):
    global NEWS_CACHE
    ticker = ticker.upper().strip()
    
    # Check Cache
    current_time = time.time()
    if ticker in NEWS_CACHE:
        cached_data, timestamp = NEWS_CACHE[ticker]
        if current_time - timestamp < CACHE_TTL:
            return cached_data

    # Fetch Short Name via yfinance to improve search quality
    try:
        info = yf.Ticker(ticker).info
        short_name = info.get('shortName', '').split(' ')[0] if info.get('shortName') else ''
    except:
        short_name = ''

    aggregated_news = []
    
    # Fetch in parallel for speed
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        f_google = executor.submit(fetch_google_news, ticker, short_name)
        f_ddg = executor.submit(fetch_duckduckgo_news, ticker, short_name)
        f_finnhub = executor.submit(fetch_finnhub_news, ticker)
        f_alpha = executor.submit(fetch_alphavantage_news, ticker)
        
        aggregated_news.extend(f_google.result())
        aggregated_news.extend(f_finnhub.result())
        aggregated_news.extend(f_ddg.result())
        aggregated_news.extend(f_alpha.result())

    # Deduplicate by Title (loose match)
    unique_news = []
    seen_titles = set()
    for item in aggregated_news:
        normalized_title = "".join([c.lower() for c in item['title'] if c.isalnum() or c.isspace()]).strip()
        if normalized_title not in seen_titles:
            seen_titles.add(normalized_title)
            unique_news.append(item)


    unique_news.sort(key=lambda x: parse_date(x['pubDate']), reverse=True)
    
    final_feed = unique_news[:15]
    
    # Update Cache
    NEWS_CACHE[ticker] = (final_feed, current_time)
    
    return final_feed

def fetch_corporate_news(ticker):
    """Fetch official press releases and earnings announcements using Google News RSS search."""
    global CORP_NEWS_CACHE
    ticker = ticker.upper().strip()
    
    # Check Cache
    current_time = time.time()
    if ticker in CORP_NEWS_CACHE:
        cached_data, timestamp = CORP_NEWS_CACHE[ticker]
        if current_time - timestamp < CACHE_TTL:
            return cached_data
            
    try:
        info = yf.Ticker(ticker).info
        company_name = info.get('shortName', '').split(' ')[0] if info.get('shortName') else ticker
    except:
        company_name = ticker
        
    query = f"{company_name} press release OR earnings OR corporate announcement OR dividend"
    url = f"https://news.google.com/rss/search?q={urllib.parse.quote(query)}&hl=en-US&gl=US&ceid=US:en"
    
    news = []
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=5) as response:
            tree = ET.parse(response)
            root = tree.getroot()
            count = 0
            for item in root.findall('./channel/item'):
                if count >= 10: break
                title = item.find('title').text if item.find('title') is not None else "Corporate Update"
                link = item.find('link').text if item.find('link') is not None else "#"
                source = item.find('source').text if item.find('source') is not None else "PR Wire"
                pubDate = item.find('pubDate').text if item.find('pubDate') is not None else ""
                
                # Check if it looks like actual corporate/earnings release
                title_lower = title.lower()
                is_pr = any(x in title_lower for x in ["press release", "earnings", "announces", "dividend", "report", "sec filing", "form 8-k", "partnership", "acquire", "merger", "joins", "launches", "unveils", "team up"])
                
                news.append({
                    "title": title,
                    "link": link,
                    "publisher": f"PR Alert ({source})",
                    "pubDate": pubDate,
                    "is_pr": is_pr
                })
                count += 1
    except Exception as e:
        print(f"Corporate News error: {e}")
        
    # Sort PR matches first, then date
    news.sort(key=lambda x: (x.get('is_pr', False), parse_date(x['pubDate'])), reverse=True)
    
    # Save to Cache
    CORP_NEWS_CACHE[ticker] = (news, current_time)
    return news
