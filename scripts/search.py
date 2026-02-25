#!/usr/bin/env python3
"""
search.py - Job URL Processor & Organization Searcher

PRIMARY: Reads data/job-links.txt, fetches each job posting, extracts metadata.
SECONDARY: Reads data/target-orgs.txt and searches career pages for matching roles.
Outputs structured JSON to data/raw-jobs.json.
"""

import json
import os
import re
import sys
import time
import hashlib
from datetime import datetime
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

# Paths relative to project root
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JOB_LINKS_FILE = os.path.join(BASE_DIR, "data", "job-links.txt")
TARGET_ORGS_FILE = os.path.join(BASE_DIR, "data", "target-orgs.txt")
RAW_JOBS_FILE = os.path.join(BASE_DIR, "data", "raw-jobs.json")
APPLICATIONS_FILE = os.path.join(BASE_DIR, "data", "applications.json")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
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


def load_existing_urls() -> set:
    """Load URLs already tracked in applications.json to avoid duplicates."""
    if not os.path.exists(APPLICATIONS_FILE):
        return set()
    try:
        with open(APPLICATIONS_FILE) as f:
            apps = json.load(f)
        return {a.get("url", "") for a in apps}
    except (json.JSONDecodeError, IOError):
        return set()


def is_cap_exempt_likely(url: str, text: str) -> bool:
    """Heuristically determine if an employer is likely cap-exempt."""
    combined = (url + " " + text).lower()
    return any(signal in combined for signal in CAP_EXEMPT_SIGNALS)


def detect_sponsorship_flags(text: str) -> list:
    """Return list of sponsorship-related phrases found in text."""
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
    """Extract salary range from job text."""
    patterns = [
        r"\$[\d,]+(?:\s*[-–]\s*\$[\d,]+)?(?:\s*(?:per year|/year|annually|/yr))?",
        r"[\d,]+(?:k|K)(?:\s*[-–]\s*[\d,]+(?:k|K))?",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(0).strip()
    return ""


def fetch_job_page(url: str) -> dict | None:
    """Fetch a single job posting URL and extract structured data."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"  [ERROR] Failed to fetch {url}: {e}", file=sys.stderr)
        return None

    soup = BeautifulSoup(resp.text, "html.parser")

    # Remove script/style noise
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()

    full_text = soup.get_text(separator=" ", strip=True)

    # Try to extract title
    title = ""
    for selector in ["h1", "h2", '[class*="job-title"]', '[class*="jobtitle"]', "title"]:
        el = soup.select_one(selector)
        if el:
            title = el.get_text(strip=True)
            break

    # Try to extract company/org name
    company = ""
    domain = urlparse(url).netloc
    for part in domain.split("."):
        if part not in ("www", "com", "org", "edu", "gov", "net", "jobs", "careers"):
            company = part.capitalize()
            break

    # Location hints
    location = "Remote/USA"
    loc_match = re.search(
        r"\b(remote|[A-Z][a-z]+,\s*[A-Z]{2}|[A-Z][a-z]+\s+[A-Z][a-z]+,\s*[A-Z]{2})\b",
        full_text,
    )
    if loc_match:
        location = loc_match.group(0)

    return {
        "id": hashlib.md5(url.encode()).hexdigest()[:12],
        "title": title[:200],
        "company": company,
        "location": location,
        "url": url,
        "description": full_text[:8000],
        "date_posted": datetime.now().strftime("%Y-%m-%d"),
        "salary": extract_salary(full_text),
        "cap_exempt_likely": is_cap_exempt_likely(url, full_text),
        "sponsorship_flags": detect_sponsorship_flags(full_text),
        "source": "job-links.txt",
    }


def read_job_links() -> list:
    """Read non-comment, non-blank URLs from job-links.txt."""
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
    """
    Search an organization's career page for matching software roles.
    Simple static HTML scraping; falls back gracefully on JS-heavy sites.
    """
    jobs = []
    print(f"  Searching {org_url} ...", flush=True)
    try:
        resp = requests.get(org_url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"  [WARN] Could not reach {org_url}: {e}", file=sys.stderr)
        return jobs

    soup = BeautifulSoup(resp.text, "html.parser")

    # Find links that look like job postings
    seen_hrefs = set()
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        text = a.get_text(strip=True).lower()

        # Check if the link text mentions a matching role
        if not any(kw in text for kw in ROLE_KEYWORDS):
            continue

        # Build absolute URL
        full_url = urljoin(org_url, href)
        if full_url in seen_hrefs:
            continue
        seen_hrefs.add(full_url)

        job = fetch_job_page(full_url)
        if job:
            job["source"] = "target-orgs.txt"
            jobs.append(job)
            time.sleep(1)  # polite crawling

    return jobs


def read_target_orgs() -> list:
    """Read non-comment, non-blank URLs from target-orgs.txt."""
    if not os.path.exists(TARGET_ORGS_FILE):
        return []
    urls = []
    with open(TARGET_ORGS_FILE) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                urls.append(line)
    return urls


def load_existing_raw_jobs() -> list:
    """Load any previously fetched jobs to avoid re-fetching."""
    if not os.path.exists(RAW_JOBS_FILE):
        return []
    try:
        with open(RAW_JOBS_FILE) as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return []


def main():
    print("=== Phase 1: Job Discovery ===", flush=True)

    existing_app_urls = load_existing_urls()
    existing_raw = load_existing_raw_jobs()
    existing_raw_urls = {j["url"] for j in existing_raw}

    all_jobs = list(existing_raw)

    # --- PRIMARY: Process job-links.txt ---
    job_links = read_job_links()
    if job_links:
        print(f"\n[PRIMARY] Processing {len(job_links)} URL(s) from job-links.txt ...", flush=True)
        for url in job_links:
            if url in existing_app_urls:
                print(f"  SKIP (already applied): {url}")
                continue
            if url in existing_raw_urls:
                print(f"  SKIP (already fetched): {url}")
                continue
            print(f"  Fetching: {url}", flush=True)
            job = fetch_job_page(url)
            if job:
                all_jobs.append(job)
                existing_raw_urls.add(url)
                print(f"  -> Found: {job['title']} @ {job['company']}")
            time.sleep(2)
    else:
        print("\n[PRIMARY] job-links.txt is empty or has no URLs.")

    # --- SECONDARY: Search target-orgs.txt (only if no primary jobs found) ---
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

    # Save
    with open(RAW_JOBS_FILE, "w") as f:
        json.dump(unique_jobs, f, indent=2)

    print(f"\n[DONE] {len(unique_jobs)} total job(s) saved to data/raw-jobs.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
