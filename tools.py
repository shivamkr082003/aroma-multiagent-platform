import os
import re
import json
from urllib.parse import urljoin, urlparse
from dotenv import load_dotenv
import requests
from bs4 import BeautifulSoup
from langchain.tools import tool
from tavily import TavilyClient

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
#  SCRAPING HELPERS & PARSING
# ===========================

MIN_USABLE_TEXT_LENGTH = 300

PHONE_PATTERNS = [
    # Indian mobile: +91 99111 13610, +91-99111-13610, +919911113610, 09911113610, 9911113610
    r'(?:(?:\+|00)91[\s.-]?)?(?:0)?[6-9]\d{4}[\s.-]?\d{5}\b',
    r'(?:(?:\+|00)91[\s.-]?)?(?:0)?[6-9]\d{2}[\s.-]?\d{3}[\s.-]?\d{4}\b',
    # Indian landline with STD codes: +91 11 2345 6789, 011-23456789
    r'(?:(?:\+|00)91[\s.-]?)?(?:0\d{2,4}[\s.-]?)?\d{6,8}\b',
    # US/Canada: +1 (800) 555-0199, (555) 123-4567, 555-123-4567
    r'(?:\+?1[\s.-]?)?\(?[2-9]\d{2}\)?[\s.-]?\d{3}[\s.-]?\d{4}\b',
    # General International format
    r'\+(?:[1-9]\d{0,2})[\s.-]?\(?\d{1,4}\)?[\s.-]?\d{2,4}[\s.-]?\d{2,4}(?:[\s.-]?\d{1,4})?\b',
]

EMAIL_PATTERN = re.compile(r'\b[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+\b')


def _extract_page_details(html: str, source_url: str) -> str:
    """
    Deterministically extract structured and full content from raw HTML:
    - Page Title & Meta Description
    - Direct phone/email links (<a href="tel:...">, <a href="mailto:...">)
    - Regex-extracted Indian and international phone numbers & emails
    - Footer & Address sections
    - JSON-LD structured schema metadata
    - Main readable text
    """
    soup = BeautifulSoup(html, 'html.parser')

    # 1. Title
    title = ''
    if soup.title and soup.title.string:
        title = soup.title.string.strip()
    elif soup.find('h1'):
        title = soup.find('h1').get_text(separator=' ', strip=True)

    # 2. Meta description
    meta_desc = ''
    meta_tag = soup.find('meta', attrs={'name': re.compile(r'description', re.I)}) or soup.find('meta', attrs={'property': 'og:description'})
    if meta_tag and meta_tag.get('content'):
        meta_desc = meta_tag['content'].strip()

    # 3. JSON-LD Structured Data
    structured_data = []
    json_ld_contacts = {'phones': [], 'emails': [], 'addresses': [], 'names': []}
    for s in soup.find_all('script', type='application/ld+json'):
        try:
            raw_json = s.string or s.text
            if raw_json:
                data = json.loads(raw_json)
                structured_data.append(data)

                def scan_schema(obj):
                    if isinstance(obj, dict):
                        if 'telephone' in obj and obj['telephone']:
                            json_ld_contacts['phones'].append(str(obj['telephone']))
                        if 'email' in obj and obj['email']:
                            json_ld_contacts['emails'].append(str(obj['email']))
                        if 'name' in obj and obj['name'] and obj.get('@type') in ['Organization', 'LocalBusiness', 'Corporation', 'Company']:
                            json_ld_contacts['names'].append(str(obj['name']))
                        if 'address' in obj:
                            addr = obj['address']
                            if isinstance(addr, dict):
                                parts = [str(v) for k, v in addr.items() if k != '@type' and v]
                                json_ld_contacts['addresses'].append(', '.join(parts))
                            elif isinstance(addr, str):
                                json_ld_contacts['addresses'].append(addr)
                        for v in obj.values():
                            scan_schema(v)
                    elif isinstance(obj, list):
                        for item in obj:
                            scan_schema(item)

                scan_schema(data)
        except Exception:
            pass

    # 4. Explicit Links (tel:, mailto:, and key subpages)
    tel_links = []
    mailto_links = []
    nav_links = []
    for a in soup.find_all('a', href=True):
        href = a['href'].strip()
        text = a.get_text(separator=' ', strip=True)
        if href.lower().startswith('tel:'):
            val = href[4:].strip()
            if val and val not in tel_links:
                tel_links.append(val)
        elif href.lower().startswith('mailto:'):
            val = href[7:].split('?')[0].strip()
            if val and val not in mailto_links:
                mailto_links.append(val)
        elif any(k in href.lower() or k in text.lower() for k in ['contact', 'about', 'pricing', 'team', 'service', 'faq', 'support']):
            full_href = urljoin(source_url, href)
            label = f"{text} ({full_href})" if text else full_href
            if label not in nav_links and len(nav_links) < 12:
                nav_links.append(label)

    # 5. Extract Footer & Address sections explicitly
    footer_texts = []
    for f_tag in soup.find_all(['footer', 'address']):
        t = f_tag.get_text(separator=' ', strip=True)
        if t and t not in footer_texts:
            footer_texts.append(t)

    for c_elem in soup.find_all(attrs={'id': re.compile(r'contact|footer|address|location', re.I)}):
        if c_elem.name not in ['footer', 'address']:
            t = c_elem.get_text(separator=' ', strip=True)
            if t and len(t) < 1200 and t not in footer_texts:
                footer_texts.append(t)

    # 6. Extract full clean body text (NEVER delete footer, nav, header!)
    for tag in soup(['script', 'style', 'noscript', 'svg', 'iframe', 'canvas']):
        tag.decompose()

    body_text = soup.get_text(separator='\n', strip=True)
    body_text_clean = re.sub(r'\n{3,}', '\n\n', body_text)
    combined_scan_text = body_text_clean + '\n' + html

    # 7. Deterministic Phone Extraction
    phone_candidates = set(tel_links)
    for p in json_ld_contacts['phones']:
        phone_candidates.add(p)

    for pat in PHONE_PATTERNS:
        for m in re.finditer(pat, body_text_clean):
            cand = m.group(0).strip(' .,;:()/-')
            digits = re.sub(r'\D', '', cand)
            # Valid phone length check (8 to 15 digits) and filter out obvious years
            if 8 <= len(digits) <= 15 and not (len(digits) == 8 and cand.startswith(('202', '201', '199'))):
                phone_candidates.add(cand)

    # Deduplicate phones by core digits while keeping cleanest formatted version
    deduped_phones = []
    seen_phone_digits = set()
    sorted_phones = sorted(phone_candidates, key=lambda x: (x.startswith('+'), len(x)), reverse=True)
    for p in sorted_phones:
        d = re.sub(r'\D', '', p)
        core = d[-10:] if len(d) >= 10 else d
        if core not in seen_phone_digits:
            seen_phone_digits.add(core)
            deduped_phones.append(p)

    # 8. Deterministic Email Extraction
    email_candidates = set(mailto_links)
    for e in json_ld_contacts['emails']:
        email_candidates.add(e)
    for m in EMAIL_PATTERN.finditer(combined_scan_text):
        em = m.group(0).strip(' .,;:()')
        if not em.lower().endswith(('.png', '.jpg', '.jpeg', '.svg', '.webp', '.gif', '.js', '.css', '.woff', '.ttf')):
            email_candidates.add(em)

    deduped_emails = sorted(list(email_candidates))

    # 9. Format structured markdown output
    output_parts = []
    output_parts.append(f"# {title or 'Webpage Content'}")
    output_parts.append(f"**URL:** {source_url}")
    if meta_desc:
        output_parts.append(f"**Description:** {meta_desc}")

    # Prominent Contact Information block
    contact_lines = []
    if deduped_phones:
        contact_lines.append(f"- **Phone Numbers:** {', '.join(deduped_phones)}")
    if deduped_emails:
        contact_lines.append(f"- **Email Addresses:** {', '.join(deduped_emails)}")
    if tel_links:
        contact_lines.append(f"- **Direct Call Links:** {', '.join(['tel:' + t for t in tel_links])}")
    if mailto_links:
        contact_lines.append(f"- **Direct Email Links:** {', '.join(['mailto:' + m for m in mailto_links])}")
    if json_ld_contacts['addresses']:
        contact_lines.append(f"- **Addresses:** {'; '.join(json_ld_contacts['addresses'])}")
    if json_ld_contacts['names']:
        contact_lines.append(f"- **Company / Organization Name:** {', '.join(json_ld_contacts['names'])}")

    if contact_lines:
        output_parts.append("\n## 📞 Contact Details & Direct Links:\n" + "\n".join(contact_lines))

    if footer_texts:
        output_parts.append("\n## 🦶 Footer & Contact Sections:\n" + "\n---\n".join(footer_texts[:3]))

    if nav_links:
        output_parts.append("\n## 🔗 Key Relevant Links:\n" + "\n".join([f"- {l}" for l in nav_links[:10]]))

    if structured_data:
        try:
            json_str = json.dumps(structured_data, indent=2)
            if len(json_str) > 1500:
                json_str = json_str[:1500] + "\n... [truncated]"
            output_parts.append(f"\n## 🏢 Structured Schema Data (JSON-LD):\n```json\n{json_str}\n```")
        except Exception:
            pass

    # Full main text
    main_text = body_text_clean
    if len(main_text) > 8000:
        main_text = main_text[:8000] + "\n\n... [Remaining content truncated for brevity]"
    output_parts.append(f"\n## 📄 Page Content:\n{main_text}")

    return "\n\n".join(output_parts)


def _scrape_with_beautifulsoup(url: str) -> tuple[str, bool]:
    """Fast path: standard HTTP GET + BeautifulSoup parsing."""
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }
    resp = requests.get(url, timeout=10, headers=headers)
    resp.raise_for_status()
    if resp.encoding is None or resp.encoding == 'ISO-8859-1':
        resp.encoding = resp.apparent_encoding or 'utf-8'

    html = resp.text
    extracted = _extract_page_details(html, url)
    # Check if page is an empty SPA shell (very short visible text)
    is_sufficient = len(extracted) >= MIN_USABLE_TEXT_LENGTH
    return extracted, is_sufficient


def _scrape_with_playwright(url: str) -> str:
    """
    Fallback path: render page in headless Playwright Chromium to execute
    client-side JavaScript before parsing.
    """
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 800},
        )
        page = context.new_page()
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=20000)
            page.wait_for_timeout(1500)
            html = page.content()
        finally:
            browser.close()

    return _extract_page_details(html, url)


@tool
def scrape_url(url: str) -> str:
    """
    Read and extract comprehensive content and contact details from a webpage.

    Extracts:
    - Title, meta description, and main body text
    - Phone numbers (Indian & International formats)
    - Email addresses and direct mailto links
    - Phone call links (tel: links)
    - Footer, address, and location details
    - JSON-LD structured schema metadata

    Input:
        A valid HTTP or HTTPS URL.

    Output:
        Rich structured markdown containing contact information, footers,
        and readable page content.
    """
    # Normalize URL scheme
    url = url.strip()
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    # 1. Fast path: try lightweight HTTP request first
    bs_result = ""
    bs_error = None
    try:
        bs_result, is_sufficient = _scrape_with_beautifulsoup(url)
        if is_sufficient:
            return bs_result
    except Exception as e:
        bs_error = str(e)

    # 2. Fallback: page returned little content or HTTP failed (SPA/JS rendering)
    try:
        pw_result = _scrape_with_playwright(url)
        if pw_result and len(pw_result) >= MIN_USABLE_TEXT_LENGTH:
            return pw_result
        if bs_result:
            return bs_result
        return (
            f"Could not extract meaningful content from {url}. "
            "The page may require authentication, be protected by anti-bot verification, or be empty."
        )
    except Exception as pw_error:
        if bs_result:
            return bs_result
        return (
            f"Could not scrape {url}. "
            f"HTTP error: {bs_error or 'Insufficient content'}. "
            f"Browser rendering fallback error: {pw_error}."
        )