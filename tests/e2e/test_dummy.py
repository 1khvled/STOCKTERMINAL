import pytest
import requests
from playwright.sync_api import Page, expect

def test_server_is_running(base_url):
    resp = requests.get(base_url)
    assert resp.status_code == 200

def test_playwright_dashboard(page: Page, base_url):
    page.goto(base_url)
    expect(page.locator("body")).to_be_visible()

def test_mock_data_fetch(base_url):
    resp = requests.get(f"{base_url}/api/stream?ticker=AAPL", stream=True)
    assert resp.status_code == 200
    
    events = []
    for line in resp.iter_lines():
        if line:
            events.append(line.decode('utf-8'))
            
    assert any("REDIRECT: /dashboard/AAPL" in event for event in events)
