from langchain.tools import tool
import requests
from bs4 import BeautifulSoup
from tavily import TavilyClient

import os
from dotenv import load_dotenv
load_dotenv()

tavily = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))


@tool
def web_search(query: str) -> str:
    """Search the web for recent and reliable information. Returns Titles, URLs and snippets. if the query is URL then it will return the content of the webpage."""
    results = tavily.search(query=query, max_results=5, search_depth="advanced")

    out = []

    for r in results['results']:
        out.append(
            f"Title: {r['title']}\nURL: {r['url']}\nSnippet: {r['content'][:300]}\n"
        )

    return "\n----\n".join(out)


# ===========================
#  SCRAPING HELPERS
#
#  Strategy: BeautifulSoup is fast and cheap and handles the vast
#  majority of normal pages (blogs, articles, docs, news, etc.) just
#  fine — so it stays the primary path and runs first, every time.
#
#  Some pages (LeetCode profiles, GitHub stat widgets, many React/Vue/
#  Next.js dashboards) render their actual content with JavaScript
#  AFTER the initial HTML loads. requests + BeautifulSoup only ever
#  see the empty page shell for these, no matter how good the parsing
#  is. For those — and ONLY for those — we fall back to a real headless
#  browser (Playwright) that executes the JS before reading the page.
#
#  This keeps things fast for 90% of normal scrapes while still
#  working generically on any JS-heavy site, without hardcoding any
#  specific domain.
# ===========================

# Below this many characters of extracted text, we treat the page as
# "probably an empty JS shell" and try the browser fallback.
MIN_USABLE_TEXT_LENGTH = 300


def _scrape_with_beautifulsoup(url: str) -> str:
    """Fast path: plain HTTP GET + BeautifulSoup parsing."""
    resp = requests.get(url, timeout=8, headers={"User-Agent": "Mozilla/5.0"})
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    for tag in soup(["script", "style", "nav", "footer"]):
        tag.decompose()
    return soup.get_text(separator=" ", strip=True)


def _scrape_with_playwright(url: str) -> str:
    """
    Fallback path: render the page in a real (headless) browser so
    JavaScript-injected content actually shows up, then parse with
    BeautifulSoup as usual.

    Only imported/used when needed, so environments that haven't
    installed playwright don't break on normal scrapes.
    """
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            )
        )
        try:
            page.goto(url, wait_until="networkidle", timeout=15000)
            # Give SPA content a moment to finish hydrating after
            # network is idle (some apps render a tick later).
            page.wait_for_timeout(1500)
            html = page.content()
        finally:
            browser.close()

    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav", "footer"]):
        tag.decompose()
    return soup.get_text(separator=" ", strip=True)


@tool
def scrape_url(url: str) -> str:
    """
    Read and extract the full text from a webpage.

    Use this tool whenever the user:
    - provides a URL
    - asks to summarize a webpage
    - asks to explain the contents of a webpage
    - asks to analyze an article or blog post

    Input:
        A valid HTTP or HTTPS URL.

    Output:
        Clean text extracted from the webpage. Works for both normal
        static pages (fast BeautifulSoup path) and JavaScript-rendered
        pages like dashboards or SPA profile pages (automatic headless
        browser fallback).
    """
    # 1. Fast path: try BeautifulSoup first, every time.
    try:
        text = _scrape_with_beautifulsoup(url)
        bs_error = None
    except Exception as e:
        text = ""
        bs_error = str(e)

    if text and len(text) >= MIN_USABLE_TEXT_LENGTH:
        return text[:3000]

    # 2. Fallback: the page looks empty/too short — likely a JS-rendered
    #    SPA shell. Try rendering it with a real browser instead.
    try:
        text = _scrape_with_playwright(url)
        if text:
            return text[:3000]
        return (
            "Could not extract meaningful content from this page even "
            "after rendering JavaScript. The page may require login, "
            "block automated browsers, or load data dynamically in a "
            "way that wasn't captured."
        )
    except Exception as playwright_error:
        # Both paths failed — report both errors for debugging.
        return (
            f"Could not scrape URL. "
            f"BeautifulSoup error: {bs_error or 'page returned too little content'}. "
            f"Playwright fallback error: {playwright_error}"
        )