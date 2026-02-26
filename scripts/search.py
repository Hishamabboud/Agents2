#!/usr/bin/env python3
"""
search.py - Job URL Processor & Organization Searcher

PRIMARY: Reads data/job-links.txt, fetches each job posting, extracts metadata.
SECONDARY: Reads data/target-orgs.txt and searches career pages for matching roles.
Outputs structured JSON to data/raw-jobs.json.

ATS coverage:
  Tier 1 (JSON API - full description):  SmartRecruiters, Greenhouse, Lever
  Tier 2 (embed/improved parse):         iCIMS, Taleo, ApplicantPro, HRMDirect,
                                          Workable, Jobvite, generic static sites
  Tier 3 (JSON-LD extraction):           Any site with schema.org JobPosting markup
  Tier 4 (best-effort HTML):             Workday, ADP, UltiPro, Oracle HCM, Paycom,
                                          Dayforce, SelectMinds (JS-heavy SPAs)
"""

import json
import os
import re
import sys
import time
import hashlib
from datetime import datetime
from urllib.parse import urljoin, urlparse, urlunparse, urlencode, parse_qs

import requests
from bs4 import BeautifulSoup

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JOB_LINKS_FILE = os.path.join(BASE_DIR, "data", "job-links.txt")
TARGET_ORGS_FILE = os.path.join(BASE_DIR, "data", "target-orgs.txt")
RAW_JOBS_FILE = os.path.join(BASE_DIR, "data", "raw-jobs.json")
APPLICATIONS_FILE = os.path.join(BASE_DIR, "data", "applications.json")
FAILED_SCRAPES_DIR = os.path.join(BASE_DIR, "data", "failed-scrapes")
MANUAL_JOBS_DIR = os.path.join(BASE_DIR, "data", "manual-jobs")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

JSON_HEADERS = {
    "User-Agent": HEADERS["User-Agent"],
    "Accept": "application/json",
    "Accept-Language": "en-US,en;q=0.5",
}

ROLE_KEYWORDS = [
    "software engineer",
    "full stack developer",
    "backend developer",
    "data engineer",
    "application developer",
    "software developer",
    "python developer",
    ".net developer",
    "database developer",
    "web developer",
]

CAP_EXEMPT_SIGNALS = [
    "university",
    "college",
    "institute of technology",
    "hospital",
    "health system",
    "medical center",
    "nonprofit",
    "non-profit",
    "foundation",
    "research institute",
    "national lab",
    "department of",
    ".gov",
    ".edu",
]

# ATSes that require JavaScript rendering (Playwright Tier 5 fallback)
PLAYWRIGHT_ATSES = {"adp", "ultipro", "oracle_hcm", "paycom", "dayforce"}

# Placeholder titles that indicate a failed/junk scrape (JS not rendered)
JUNK_TITLE_FRAGMENTS = [
    "{{",
    "are you still with us",
    "position description",
    "job description",
    "primary location",
    "our company",
    "description",
    "loading",
    "please wait",
]


def is_junk_job(job: dict) -> bool:
    """Return True if the scraped job has a placeholder/junk title."""
    title = (job.get("title") or "").strip().lower()
    if not title:
        return True
    for frag in JUNK_TITLE_FRAGMENTS:
        if title == frag or title.startswith(frag):
            return True
    return False


def log_failed_scrape(url: str, reason: str) -> None:
    """Write a stub file to data/failed-scrapes/ so the user can paste the job manually."""
    os.makedirs(FAILED_SCRAPES_DIR, exist_ok=True)
    # Derive a short filename from the domain + URL hash
    domain = urlparse(url).netloc.replace("www.", "").split(".")[0]
    url_hash = hashlib.md5(url.encode()).hexdigest()[:6]
    filename = f"{domain}_{url_hash}.txt"
    filepath = os.path.join(FAILED_SCRAPES_DIR, filename)
    if os.path.exists(filepath):
        return  # already logged
    stub = (
        f"# Failed scrape — paste job details below so the pipeline can process this posting\n"
        f"# URL:    {url}\n"
        f"# REASON: {reason}\n"
        f"# DATE:   {datetime.now().strftime('%Y-%m-%d')}\n"
        f"#\n"
        f"# Instructions:\n"
        f"#   1. Open the URL above in your browser\n"
        f"#   2. Copy the job title, company, and full job description\n"
        f"#   3. Fill in the fields below and save this file\n"
        f"#   4. Move this file to data/manual-jobs/ and re-run the pipeline\n"
        f"\n"
        f"TITLE: \n"
        f"COMPANY: \n"
        f"SALARY: \n"
        f"\n"
        f"--- JOB DESCRIPTION ---\n"
        f"\n"
    )
    with open(filepath, "w") as f:
        f.write(stub)
    print(f"  [FAILED] Stub saved → data/failed-scrapes/{filename}")


def read_manual_jobs(existing_urls: set) -> list:
    """
    Read hand-pasted job descriptions from data/manual-jobs/*.txt.
    Each file must have TITLE:, COMPANY:, and a description block after
    '--- JOB DESCRIPTION ---'.  The original URL is read from the # URL: comment.
    """
    if not os.path.isdir(MANUAL_JOBS_DIR):
        return []
    jobs = []
    for fname in sorted(os.listdir(MANUAL_JOBS_DIR)):
        if not fname.endswith(".txt"):
            continue
        fpath = os.path.join(MANUAL_JOBS_DIR, fname)
        with open(fpath) as f:
            raw = f.read()

        # Extract URL from comment line
        url = ""
        for line in raw.splitlines():
            if line.startswith("# URL:"):
                url = line.replace("# URL:", "").strip()
                break

        if not url or url in existing_urls:
            continue

        # Parse fields
        title = ""
        company = ""
        salary = ""
        description_lines = []
        in_desc = False
        for line in raw.splitlines():
            if line.startswith("TITLE:") and not in_desc:
                title = line.replace("TITLE:", "").strip()
            elif line.startswith("COMPANY:") and not in_desc:
                company = line.replace("COMPANY:", "").strip()
            elif line.startswith("SALARY:") and not in_desc:
                salary = line.replace("SALARY:", "").strip()
            elif line.strip() == "--- JOB DESCRIPTION ---":
                in_desc = True
            elif in_desc:
                description_lines.append(line)

        description = "\n".join(description_lines).strip()
        if not title or not description:
            print(f"  [MANUAL] SKIP {fname} — missing TITLE or description")
            continue

        job = {
            "url": url,
            "title": title,
            "company": company or urlparse(url).netloc,
            "description": description,
            "salary_text": salary,
            "ats_platform": "manual",
            "extraction_method": "manual",
            "fetched_at": datetime.now().isoformat(),
            "source_file": fname,
        }
        print(f"  [MANUAL] Loaded: {title} @ {company} ({fname})")
        jobs.append(job)
    return jobs

# ATS-specific CSS selectors to wait for after page load
PLAYWRIGHT_WAIT_SELECTORS = {
    "adp":        ".jobDetailsCard, #JobDetailsPanel, .job-description",
    "ultipro":    ".job-page, #JobDescriptionDiv, .job-description",
    "oracle_hcm": ".oj-flex, [data-bind*='jobDescription'], .job-requisition",
    "paycom":     ".jobDescription, .job-description, #jobDescription",
    "dayforce":   ".job-description, .jobDescription, .job-details",
}

# ATS patterns for detection
ATS_PATTERNS = {
    "workday":         ["myworkdayjobs.com", "wd1.myworkdayjobs", "wd5.myworkdayjobs",
                        "wd12.myworkdayjobs", "wd503.myworkdayjobs"],
    "icims":           [".icims.com"],
    "adp":             ["workforcenow.adp.com"],
    "ultipro":         ["recruiting.ultipro.com", "recruiting2.ultipro.com", ".rec.pro.ukg.net"],
    "paycom":          ["paycomonline.net"],
    "taleo":           [".taleo.net"],
    "dayforce":        ["dayforcehcm.com"],
    "selectminds":     ["selectminds.com"],
    "oracle_hcm":      ["oraclecloud.com/hcmUI", ".fa.us"],
    "smartrecruiters": ["jobs.smartrecruiters.com"],
    "greenhouse":      ["boards.greenhouse.io", "job.greenhouse.io"],
    "lever":           ["jobs.lever.co"],
    "workable":        ["apply.workable.com"],
    "jobvite":         ["jobs.jobvite.com"],
    "successfactors":  ["successfactors.com"],
    "jhu_workday":     ["hiring.jhu.edu"],
    "usajobs":         ["usajobs.gov"],
    "applicantpro":    ["applicantpro.com"],
}


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def detect_ats(url: str) -> str:
    url_lower = url.lower()
    for ats, patterns in ATS_PATTERNS.items():
        if any(p in url_lower for p in patterns):
            return ats
    return "generic"


def is_cap_exempt_likely(url: str, text: str) -> bool:
    combined = (url + " " + text).lower()
    return any(signal in combined for signal in CAP_EXEMPT_SIGNALS)


def detect_sponsorship_flags(text: str) -> list:
    patterns = [
        r"no sponsorship",
        r"unable to sponsor",
        r"cannot sponsor",
        r"will not sponsor",
        r"authorized to work without sponsorship",
        r"must be (a )?(us|u\.s\.) citizen",
        r"us citizen(ship)? required",
        r"permanent resident(s)? only",
        r"security clearance required",
        r"green card",
    ]
    flags = []
    text_lower = text.lower()
    for pattern in patterns:
        if re.search(pattern, text_lower):
            flags.append(pattern)
    return flags


def extract_salary(text: str) -> str:
    patterns = [
        r"\$[\d,]+(?:\s*[-–]\s*\$[\d,]+)?(?:\s*(?:per year|/year|annually|/yr))?",
        r"[\d,]+(?:k|K)(?:\s*[-–]\s*[\d,]+(?:k|K))?",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(0).strip()
    return ""


def company_from_url(url: str) -> str:
    domain = urlparse(url).netloc
    for part in domain.split("."):
        if part not in ("www", "com", "org", "edu", "gov", "net", "jobs",
                        "careers", "hiring", "apply", "job", "recruit",
                        "wd1", "wd5", "wd12", "wd503", "fa", "us6", "us2",
                        "tbe", "rec", "pro", "v4", "ats"):
            return part.capitalize()
    return domain.split(".")[0].capitalize()


def build_job(url: str, title: str, company: str, location: str,
              description: str, ats: str) -> dict:
    """Assemble the standard job dict."""
    clean_desc = description[:8000] if description else ""
    return {
        "id": hashlib.md5(url.encode()).hexdigest()[:12],
        "title": title[:200],
        "company": company,
        "location": location or "Remote/USA",
        "url": url,
        "description": clean_desc,
        "date_posted": datetime.now().strftime("%Y-%m-%d"),
        "salary": extract_salary(clean_desc),
        "cap_exempt_likely": is_cap_exempt_likely(url, clean_desc),
        "sponsorship_flags": detect_sponsorship_flags(clean_desc),
        "source": "job-links.txt",
        "ats_platform": ats,
    }


def safe_get(url: str, headers: dict = None, timeout: int = 15) -> requests.Response | None:
    try:
        resp = requests.get(url, headers=headers or HEADERS, timeout=timeout)
        resp.raise_for_status()
        return resp
    except requests.RequestException as e:
        print(f"  [WARN] GET {url}: {e}", file=sys.stderr)
        return None


def soup_text(html: str) -> str:
    """Strip scripts/styles and return plain text from HTML."""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header", "noscript"]):
        tag.decompose()
    return soup.get_text(separator=" ", strip=True)


# ---------------------------------------------------------------------------
# JSON-LD extraction (schema.org JobPosting)
# Works for: many iCIMS, some Workday, ApplicantPro, custom career sites
# ---------------------------------------------------------------------------

def extract_jsonld(url: str, html: str, ats: str) -> dict | None:
    """Try to pull a JobPosting from schema.org JSON-LD markup."""
    soup = BeautifulSoup(html, "html.parser")
    for script in soup.find_all("script", type="application/ld+json"):
        raw = script.string
        if not raw:
            continue
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue

        # Handle @graph and arrays
        items = []
        if isinstance(data, dict):
            if data.get("@graph"):
                items = data["@graph"]
            else:
                items = [data]
        elif isinstance(data, list):
            items = data

        for item in items:
            if not isinstance(item, dict):
                continue
            if item.get("@type") not in ("JobPosting", "jobPosting"):
                continue

            title = item.get("title", "") or item.get("name", "")
            raw_desc = item.get("description", "")
            description = BeautifulSoup(raw_desc, "html.parser").get_text(
                separator=" ", strip=True
            ) if raw_desc else ""

            loc_obj = item.get("jobLocation", {}) or {}
            if isinstance(loc_obj, list):
                loc_obj = loc_obj[0] if loc_obj else {}
            address = loc_obj.get("address", {}) or {}
            if isinstance(address, str):
                location = address
            else:
                city = address.get("addressLocality", "")
                state = address.get("addressRegion", "")
                location = f"{city}, {state}".strip(", ") if (city or state) else "Remote/USA"

            hiring_org = item.get("hiringOrganization", {}) or {}
            company = hiring_org.get("name", "") if isinstance(hiring_org, dict) else ""
            company = company or company_from_url(url)

            salary_raw = item.get("baseSalary", {}) or {}
            salary = ""
            if isinstance(salary_raw, dict):
                val = salary_raw.get("value", {}) or {}
                if isinstance(val, dict):
                    mn = val.get("minValue", "")
                    mx = val.get("maxValue", "")
                    if mn and mx:
                        salary = f"${mn}–${mx}"
                    elif mn:
                        salary = f"${mn}"

            if not description:
                continue  # JSON-LD present but no usable description

            desc_text = description[:8000]
            return {
                "id": hashlib.md5(url.encode()).hexdigest()[:12],
                "title": title[:200],
                "company": company,
                "location": location or "Remote/USA",
                "url": url,
                "description": desc_text,
                "date_posted": datetime.now().strftime("%Y-%m-%d"),
                "salary": salary or extract_salary(desc_text),
                "cap_exempt_likely": is_cap_exempt_likely(url, desc_text),
                "sponsorship_flags": detect_sponsorship_flags(desc_text),
                "source": "job-links.txt",
                "ats_platform": ats,
                "extraction_method": "json-ld",
            }
    return None


# ---------------------------------------------------------------------------
# ATS-specific Tier 1 fetchers (JSON APIs → full description)
# ---------------------------------------------------------------------------

def fetch_smartrecruiters(url: str) -> dict | None:
    """
    SmartRecruiters public API.
    URL:  jobs.smartrecruiters.com/{Company}/{posting_id}-{title-slug}
    API:  api.smartrecruiters.com/v1/companies/{company}/postings/{id}
    """
    m = re.search(r"smartrecruiters\.com/([^/]+)/(\d+)", url)
    if not m:
        return None
    company, posting_id = m.group(1), m.group(2)
    api_url = f"https://api.smartrecruiters.com/v1/companies/{company}/postings/{posting_id}"
    resp = safe_get(api_url, headers=JSON_HEADERS)
    if not resp:
        return None
    try:
        data = resp.json()
    except ValueError:
        return None

    # Assemble description from sections
    sections = data.get("jobAd", {}).get("sections", {}) if data.get("jobAd") else {}
    parts = []
    for key in ("companyDescription", "jobDescription", "qualifications", "additionalInformation"):
        html_part = sections.get(key, {}).get("text", "") if sections else ""
        if html_part:
            parts.append(BeautifulSoup(html_part, "html.parser").get_text(separator=" ", strip=True))
    description = "\n\n".join(parts)

    loc = data.get("location", {}) or {}
    location = loc.get("city", "") or "Remote/USA"
    if loc.get("region"):
        location = f"{location}, {loc['region']}"

    return build_job(
        url=url,
        title=data.get("name", ""),
        company=data.get("company", {}).get("name", "") or company_from_url(url),
        location=location,
        description=description,
        ats="smartrecruiters",
    ) | {"extraction_method": "api"}


def fetch_greenhouse(url: str) -> dict | None:
    """
    Greenhouse public boards API.
    URL:  boards.greenhouse.io/{company}/jobs/{id}
    API:  boards-api.greenhouse.io/v1/boards/{company}/jobs/{id}
    """
    m = re.search(r"greenhouse\.io/([^/]+)/jobs/(\d+)", url)
    if not m:
        return None
    company, job_id = m.group(1), m.group(2)
    api_url = f"https://boards-api.greenhouse.io/v1/boards/{company}/jobs/{job_id}"
    resp = safe_get(api_url, headers=JSON_HEADERS)
    if not resp:
        return None
    try:
        data = resp.json()
    except ValueError:
        return None

    raw_desc = data.get("content", "")
    description = BeautifulSoup(raw_desc, "html.parser").get_text(separator=" ", strip=True)
    location = data.get("location", {}).get("name", "Remote/USA")

    return build_job(
        url=url,
        title=data.get("title", ""),
        company=company_from_url(url),
        location=location,
        description=description,
        ats="greenhouse",
    ) | {"extraction_method": "api"}


def fetch_lever(url: str) -> dict | None:
    """
    Lever public postings API.
    URL:  jobs.lever.co/{company}/{uuid}
    API:  api.lever.co/v0/postings/{company}/{uuid}
    """
    m = re.search(r"lever\.co/([^/]+)/([0-9a-f-]{36})", url)
    if not m:
        return None
    company, posting_id = m.group(1), m.group(2)
    api_url = f"https://api.lever.co/v0/postings/{company}/{posting_id}"
    resp = safe_get(api_url, headers=JSON_HEADERS)
    if not resp:
        return None
    try:
        data = resp.json()
    except ValueError:
        return None

    parts = [data.get("description", ""), data.get("descriptionBody", "")]
    for lst in data.get("lists", []):
        parts.append(lst.get("content", ""))
    description = BeautifulSoup("\n".join(filter(None, parts)), "html.parser").get_text(
        separator=" ", strip=True
    )
    categories = data.get("categories", {}) or {}
    location = categories.get("location", "Remote/USA")

    return build_job(
        url=url,
        title=data.get("text", ""),
        company=company_from_url(url),
        location=location,
        description=description,
        ats="lever",
    ) | {"extraction_method": "api"}


# ---------------------------------------------------------------------------
# ATS-specific Tier 2 fetchers (improved HTML / embed modes)
# ---------------------------------------------------------------------------

def fetch_icims(url: str) -> dict | None:
    """
    iCIMS: strip noisy query params and request the embed/clean page.
    The '?in_iframe=1' mode returns simpler, parseable HTML.
    """
    # Extract base URL (scheme + netloc + path)
    parsed = urlparse(url)
    base = urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", "", ""))

    # Try embed mode first
    embed_url = base + "?in_iframe=1&mobile=false"
    resp = safe_get(embed_url)
    if not resp or len(resp.text) < 500:
        # Fall back to base URL
        resp = safe_get(base)
    if not resp:
        return None

    html = resp.text

    # Try JSON-LD first
    ats = "icims"
    job = extract_jsonld(url, html, ats)
    if job:
        return job

    # BeautifulSoup extraction with iCIMS-specific selectors
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header", "noscript"]):
        tag.decompose()

    title = ""
    for sel in ['[class*="job-title"]', '[id*="job-title"]', "h1", "h2"]:
        el = soup.select_one(sel)
        if el:
            title = el.get_text(strip=True)
            break

    description = ""
    for sel in [
        '[class*="iCIMS_JobContent"]',
        '[id*="jobDetail"]',
        '[class*="job-description"]',
        '[class*="description"]',
        "article",
        "main",
    ]:
        el = soup.select_one(sel)
        if el:
            description = el.get_text(separator=" ", strip=True)
            break
    if not description:
        description = soup.get_text(separator=" ", strip=True)

    if len(description) < 200:
        return None

    return build_job(
        url=url,
        title=title,
        company=company_from_url(url),
        location=_extract_location(description),
        description=description,
        ats=ats,
    ) | {"extraction_method": "html-embed"}


def fetch_taleo(url: str) -> dict | None:
    """
    Taleo: try a JSON accept header; fall back to HTML scraping.
    """
    # Taleo sometimes serves JSON with Accept: application/json
    headers_json = dict(HEADERS)
    headers_json["Accept"] = "application/json, text/javascript, */*"
    resp = safe_get(url, headers=headers_json)
    if not resp:
        return None

    # Try JSON parse
    try:
        ct = resp.headers.get("Content-Type", "")
        if "json" in ct:
            data = resp.json()
            title = (data.get("requisitionTitle") or data.get("title") or
                     data.get("jobTitle") or "")
            desc_html = (data.get("jobDescription") or data.get("description") or "")
            description = BeautifulSoup(desc_html, "html.parser").get_text(
                separator=" ", strip=True
            ) if desc_html else ""
            if title or description:
                return build_job(
                    url=url, title=title,
                    company=company_from_url(url),
                    location=_extract_location(description),
                    description=description, ats="taleo",
                ) | {"extraction_method": "api"}
    except (ValueError, AttributeError):
        pass

    html = resp.text
    # Try JSON-LD
    job = extract_jsonld(url, html, "taleo")
    if job:
        return job

    # Fallback HTML
    return _generic_html_parse(url, html, "taleo")


def fetch_workable(url: str) -> dict | None:
    """
    Workable: try their public API or fall back to JSON-LD.
    URL pattern: apply.workable.com/{company}/j/{shortcode}
    """
    m = re.search(r"workable\.com/([^/]+)/j/([A-Z0-9]+)", url, re.I)
    if m:
        company, shortcode = m.group(1), m.group(2)
        api_url = f"https://apply.workable.com/api/v3/accounts/{company}/jobs/{shortcode}"
        resp = safe_get(api_url, headers=JSON_HEADERS)
        if resp:
            try:
                data = resp.json()
                desc_html = data.get("description", "") or ""
                req_html = data.get("requirements", "") or ""
                description = (
                    BeautifulSoup(desc_html + " " + req_html, "html.parser")
                    .get_text(separator=" ", strip=True)
                )
                loc_data = data.get("location", {}) or {}
                location = loc_data.get("city") or loc_data.get("country") or "Remote/USA"
                if description:
                    return build_job(
                        url=url, title=data.get("title", ""),
                        company=data.get("company", {}).get("name", "") or company_from_url(url),
                        location=location,
                        description=description, ats="workable",
                    ) | {"extraction_method": "api"}
            except (ValueError, AttributeError):
                pass

    resp = safe_get(url)
    if not resp:
        return None
    job = extract_jsonld(url, resp.text, "workable")
    return job or _generic_html_parse(url, resp.text, "workable")


def fetch_jobvite(url: str) -> dict | None:
    """Jobvite: try JSON API then fall back to HTML + JSON-LD."""
    # Try JSON endpoint
    json_url = re.sub(r"\?.*", "", url) + "?format=json"
    resp = safe_get(json_url, headers=JSON_HEADERS)
    if resp:
        try:
            ct = resp.headers.get("Content-Type", "")
            if "json" in ct:
                data = resp.json()
                desc_html = data.get("jobDescription", "") or data.get("description", "") or ""
                description = BeautifulSoup(desc_html, "html.parser").get_text(
                    separator=" ", strip=True
                )
                if description:
                    return build_job(
                        url=url, title=data.get("title", ""),
                        company=company_from_url(url),
                        location=data.get("jobLocation", "Remote/USA"),
                        description=description, ats="jobvite",
                    ) | {"extraction_method": "api"}
        except (ValueError, AttributeError):
            pass

    resp = safe_get(url)
    if not resp:
        return None
    job = extract_jsonld(url, resp.text, "jobvite")
    return job or _generic_html_parse(url, resp.text, "jobvite")


# ---------------------------------------------------------------------------
# Playwright Tier 5 – JS-heavy ATSes (ADP, UltiPro, Oracle HCM, Paycom, Dayforce)
# ---------------------------------------------------------------------------

# Module-level browser/context, shared across all calls in one run
_pw = None          # playwright instance
_pw_browser = None  # browser instance
_pw_context = None  # browser context (with proxy)


def _get_playwright_proxy() -> dict | None:
    """Parse proxy credentials from HTTPS_PROXY env var for Playwright."""
    from urllib.parse import urlparse as _urlparse
    raw = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy", "")
    if not raw:
        return None
    p = _urlparse(raw)
    if not p.hostname:
        return None
    proxy = {"server": f"http://{p.hostname}:{p.port}"}
    if p.username:
        proxy["username"] = p.username
    if p.password:
        proxy["password"] = p.password
    return proxy


def init_playwright():
    """Launch a shared Playwright browser for JS-heavy scraping."""
    global _pw, _pw_browser, _pw_context
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("  [WARN] playwright not installed; JS-heavy ATSes will be skipped.",
              file=sys.stderr)
        return

    import glob as _glob
    # Find the chromium executable (support both headless-shell and full chrome)
    candidates = sorted(_glob.glob(
        "/root/.cache/ms-playwright/chromium*/chrome-linux/chrome"
    ), reverse=True)
    exe = candidates[0] if candidates else None

    try:
        _pw = sync_playwright().start()
        launch_kwargs = {"headless": True}
        if exe:
            launch_kwargs["executable_path"] = exe
        _pw_browser = _pw.chromium.launch(**launch_kwargs)
        proxy = _get_playwright_proxy()
        _pw_context = _pw_browser.new_context(
            proxy=proxy or {},
            ignore_https_errors=True,
            user_agent=HEADERS["User-Agent"],
            viewport={"width": 1280, "height": 800},
        )
        print("  [playwright] Browser ready" + (f" (exe: {exe})" if exe else ""),
              flush=True)
    except Exception as e:
        print(f"  [WARN] Could not start Playwright browser: {e}", file=sys.stderr)
        _pw = _pw_browser = _pw_context = None


def close_playwright():
    """Shut down the shared Playwright browser."""
    global _pw, _pw_browser, _pw_context
    try:
        if _pw_browser:
            _pw_browser.close()
        if _pw:
            _pw.stop()
    except Exception:
        pass
    _pw = _pw_browser = _pw_context = None


def fetch_with_playwright(url: str, ats: str) -> dict | None:
    """
    Use the shared Playwright browser to render a JS-heavy ATS page,
    then extract content via JSON-LD → generic HTML parse.
    """
    if _pw_context is None:
        return None

    try:
        from playwright.sync_api import TimeoutError as PWTimeout
    except ImportError:
        return None

    try:
        page = _pw_context.new_page()
        try:
            page.goto(url, wait_until="networkidle", timeout=30000)
        except PWTimeout:
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=20000)
            except PWTimeout:
                page.close()
                return None

        # ATS-specific element wait (best-effort)
        selector = PLAYWRIGHT_WAIT_SELECTORS.get(ats, "")
        if selector:
            try:
                page.wait_for_selector(selector, timeout=8000)
            except PWTimeout:
                pass  # content may still be present

        # Extra settle time for React/Angular hydration
        page.wait_for_timeout(2000)
        html = page.content()
        page.close()
    except Exception as e:
        print(f"  [WARN] Playwright error ({ats}): {e}", file=sys.stderr)
        return None

    # Try JSON-LD first (some ATSes inject it after JS load)
    job = extract_jsonld(url, html, ats)
    if job:
        job["extraction_method"] = "playwright-jsonld"
        return job

    # Generic rendered-HTML parse
    job = _generic_html_parse(url, html, ats)
    if job:
        job["extraction_method"] = "playwright-html"
        return job

    return None


# ---------------------------------------------------------------------------
# Generic fetchers
# ---------------------------------------------------------------------------

def _extract_location(text: str) -> str:
    """Pull first location-looking string from text."""
    m = re.search(
        r"\b(remote|[A-Z][a-z]+ ?,\s*[A-Z]{2}|[A-Z][a-z]+ [A-Z][a-z]+,\s*[A-Z]{2})\b",
        text,
    )
    return m.group(0) if m else "Remote/USA"


def _extract_title(soup: BeautifulSoup) -> str:
    for sel in [
        "h1",
        '[class*="job-title"]',
        '[class*="jobtitle"]',
        '[class*="position-title"]',
        '[id*="job-title"]',
        "h2",
        "title",
    ]:
        el = soup.select_one(sel)
        if el:
            txt = el.get_text(strip=True)
            if 5 < len(txt) < 200:
                return txt
    return ""


def _extract_description(soup: BeautifulSoup) -> str:
    """Try common job description container selectors before falling back to full text."""
    for sel in [
        '[class*="job-description"]',
        '[class*="jobDescription"]',
        '[class*="job-details"]',
        '[class*="description"]',
        '[id*="job-description"]',
        '[id*="jobDescription"]',
        '[id*="description"]',
        "article",
        "main",
        '[role="main"]',
        ".content",
        "#content",
    ]:
        el = soup.select_one(sel)
        if el:
            txt = el.get_text(separator=" ", strip=True)
            if len(txt) > 300:
                return txt
    return soup.get_text(separator=" ", strip=True)


def _generic_html_parse(url: str, html: str, ats: str) -> dict | None:
    """BeautifulSoup extraction with improved selectors."""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header", "noscript"]):
        tag.decompose()

    title = _extract_title(soup)
    description = _extract_description(soup)

    if len(description) < 200:
        return None

    return build_job(
        url=url,
        title=title,
        company=company_from_url(url),
        location=_extract_location(description),
        description=description,
        ats=ats,
    ) | {"extraction_method": "html"}


def fetch_job_page(url: str) -> dict | None:
    """
    Main entry point. Routes to the best fetcher for each ATS,
    then falls back through JSON-LD → HTML extraction.
    """
    ats = detect_ats(url)
    print(f"  [ATS={ats}] {url[:80]}", flush=True)

    # Tier 1 – JSON API (complete descriptions)
    if ats == "smartrecruiters":
        job = fetch_smartrecruiters(url)
        if job:
            return job

    elif ats == "greenhouse":
        job = fetch_greenhouse(url)
        if job:
            return job

    elif ats == "lever":
        job = fetch_lever(url)
        if job:
            return job

    # Tier 2 – ATS-aware HTML / embed
    elif ats == "icims":
        job = fetch_icims(url)
        if job:
            return job
        # If icims fetch failed completely, fall through to generic below

    elif ats == "taleo":
        job = fetch_taleo(url)
        if job:
            return job

    elif ats == "workable":
        job = fetch_workable(url)
        if job:
            return job

    elif ats == "jobvite":
        job = fetch_jobvite(url)
        if job:
            return job

    # Tier 3 + 4 – fetch page HTML, try JSON-LD first, then generic BS4
    # Covers: workday, adp, ultipro, oracle_hcm, paycom, dayforce,
    #         selectminds, successfactors, jhu_workday, usajobs,
    #         applicantpro, generic
    resp = safe_get(url)
    if not resp:
        return None

    html = resp.text

    job = extract_jsonld(url, html, ats)
    if job:
        return job

    job = _generic_html_parse(url, html, ats)
    if job:
        return job

    # Tier 5 – Playwright for JS-heavy ATSes
    if ats in PLAYWRIGHT_ATSES:
        job = fetch_with_playwright(url, ats)
        if job:
            return job

    print(f"  [SKIP] Could not extract meaningful content (JS-heavy ATS: {ats})",
          file=sys.stderr)
    return None


# ---------------------------------------------------------------------------
# I/O helpers
# ---------------------------------------------------------------------------

def load_existing_urls() -> set:
    if not os.path.exists(APPLICATIONS_FILE):
        return set()
    try:
        with open(APPLICATIONS_FILE) as f:
            apps = json.load(f)
        return {a.get("url", "") for a in apps}
    except (json.JSONDecodeError, IOError):
        return set()


def load_existing_raw_jobs() -> list:
    if not os.path.exists(RAW_JOBS_FILE):
        return []
    try:
        with open(RAW_JOBS_FILE) as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return []


def read_job_links() -> list:
    if not os.path.exists(JOB_LINKS_FILE):
        return []
    urls = []
    with open(JOB_LINKS_FILE) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                urls.append(line)
    return urls


def search_org_career_page(org_url: str) -> list:
    """Search an organization career page for matching roles (static HTML only)."""
    jobs = []
    print(f"  Searching {org_url} ...", flush=True)
    resp = safe_get(org_url)
    if not resp:
        return jobs

    soup = BeautifulSoup(resp.text, "html.parser")
    seen_hrefs = set()
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        text = a.get_text(strip=True).lower()
        if not any(kw in text for kw in ROLE_KEYWORDS):
            continue
        full_url = urljoin(org_url, href)
        if full_url in seen_hrefs:
            continue
        seen_hrefs.add(full_url)
        job = fetch_job_page(full_url)
        if job:
            job["source"] = "target-orgs.txt"
            jobs.append(job)
            time.sleep(1)
    return jobs


def read_target_orgs() -> list:
    if not os.path.exists(TARGET_ORGS_FILE):
        return []
    urls = []
    with open(TARGET_ORGS_FILE) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                urls.append(line)
    return urls


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("=== Phase 1: Job Discovery ===", flush=True)

    # Start Playwright browser for JS-heavy ATSes
    init_playwright()

    existing_app_urls = load_existing_urls()
    existing_raw = load_existing_raw_jobs()
    existing_raw_urls = {j["url"] for j in existing_raw}

    all_jobs = list(existing_raw)

    # --- MANUAL JOBS: inject hand-pasted descriptions before primary scraping ---
    manual_jobs = read_manual_jobs(existing_raw_urls | existing_app_urls)
    for mj in manual_jobs:
        all_jobs.append(mj)
        existing_raw_urls.add(mj["url"])

    # --- PRIMARY: Process job-links.txt ---
    job_links = read_job_links()
    if job_links:
        print(f"\n[PRIMARY] Processing {len(job_links)} URL(s) from job-links.txt ...", flush=True)
        stats = {"fetched": 0, "skipped_app": 0, "skipped_raw": 0, "failed": 0, "junk": 0}
        ats_summary: dict[str, int] = {}

        for url in job_links:
            if url in existing_app_urls:
                print(f"  SKIP (already applied): {url[:80]}")
                stats["skipped_app"] += 1
                continue
            if url in existing_raw_urls:
                print(f"  SKIP (already fetched): {url[:80]}")
                stats["skipped_raw"] += 1
                continue

            job = fetch_job_page(url)
            if job:
                if is_junk_job(job):
                    junk_title = job.get("title", "(no title)")
                    print(f"  [JUNK] '{junk_title}' — placeholder content detected")
                    log_failed_scrape(url, f"Junk/placeholder title: '{junk_title}'")
                    stats["junk"] += 1
                    # Still add to raw-jobs so we don't re-fetch every run
                    all_jobs.append(job)
                    existing_raw_urls.add(url)
                else:
                    all_jobs.append(job)
                    existing_raw_urls.add(url)
                    ats = job.get("ats_platform", "generic")
                    ats_summary[ats] = ats_summary.get(ats, 0) + 1
                    method = job.get("extraction_method", "html")
                    print(f"  -> [{method}] {job['title'] or '(no title)'} @ {job['company']}")
                    stats["fetched"] += 1
            else:
                log_failed_scrape(url, "Could not extract content (JS wall, auth, or 404)")
                stats["failed"] += 1

            time.sleep(2)

        print(f"\n[PRIMARY SUMMARY]")
        print(f"  Fetched:   {stats['fetched']}")
        print(f"  Junk:      {stats['junk']}  (stubs saved to data/failed-scrapes/)")
        print(f"  Failed:    {stats['failed']}  (stubs saved to data/failed-scrapes/)")
        print(f"  Skipped:   {stats['skipped_app'] + stats['skipped_raw']}")
        if ats_summary:
            print("  By ATS:    " + ", ".join(f"{k}={v}" for k, v in sorted(ats_summary.items())))
    else:
        print("\n[PRIMARY] job-links.txt is empty or has no URLs.")

    # --- SECONDARY: Search target-orgs.txt (only if no primary jobs) ---
    if not job_links:
        org_urls = read_target_orgs()
        if org_urls:
            print(
                f"\n[SECONDARY] Searching {len(org_urls)} organization(s) from target-orgs.txt ...",
                flush=True,
            )
            for org_url in org_urls:
                found = search_org_career_page(org_url)
                for job in found:
                    if job["url"] not in existing_raw_urls and job["url"] not in existing_app_urls:
                        all_jobs.append(job)
                        existing_raw_urls.add(job["url"])
                        print(f"  -> Found: {job['title']} @ {job['company']}")
                time.sleep(3)
        else:
            print("\n[SECONDARY] target-orgs.txt is empty.")

    # Deduplicate by URL
    seen = set()
    unique_jobs = []
    for job in all_jobs:
        if job["url"] not in seen:
            seen.add(job["url"])
            unique_jobs.append(job)

    # Shut down Playwright browser
    close_playwright()

    with open(RAW_JOBS_FILE, "w") as f:
        json.dump(unique_jobs, f, indent=2)

    print(f"\n[DONE] {len(unique_jobs)} total job(s) saved to data/raw-jobs.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
