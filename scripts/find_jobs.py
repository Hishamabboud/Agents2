#!/usr/bin/env python3
"""
Job Finder Script — Mohamad Abboud
Searches job boards across US, Canada, Netherlands, and Scotland
for roles matching the candidate's skills, requiring visa sponsorship.
Outputs results to output/job-leads.txt
"""

import json
import os
import re
import time
import urllib.request
import urllib.parse
from datetime import datetime
from html.parser import HTMLParser


# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────

OUTPUT_FILE = os.path.join(os.path.dirname(__file__), '..', 'output', 'job-leads.txt')
LEADS_SEEN_FILE = os.path.join(os.path.dirname(__file__), '..', 'data', 'seen-leads.json')

CANDIDATE_SKILLS = [
    'python', 'flask', 'c#', 'asp.net', '.net', 'php',
    'javascript', 'vue', 'react', 'angular', 'html', 'css',
    'sql', 'postgresql', 'mysql', 'sql server', 't-sql', 'stored procedures',
    'etl', 'data engineer', 'data migration', 'rest api', 'restful',
    'docker', 'git', 'ci/cd', 'agile', 'scrum', 'full stack', 'backend',
]

TARGET_ROLES = [
    'software engineer', 'full stack developer', 'backend developer',
    'data engineer', 'database developer', 'python developer',
    '.net developer', 'application developer', 'software developer',
    'web developer', 'api developer', 'systems developer',
]

DEALBREAKER_PHRASES = [
    'no sponsorship', 'unable to sponsor', 'cannot sponsor',
    'must be authorized to work without sponsorship',
    'must be a us citizen', 'must be us citizen',
    'us citizen or permanent resident only',
    'citizens and permanent residents only',
    'must have right to work in the uk',
    'must have valid work authorization',
    'eu citizen only', 'eu citizens only',
    'security clearance required', 'secret clearance',
    'top secret clearance', 'ts/sci',
]

US_SPONSORSHIP_SIGNALS = [
    'university', 'college', 'institute of technology', 'usajobs',
    'government', 'nonprofit', 'non-profit', '501(c)', 'research lab',
    'national laboratory', 'national lab',
]

INTL_SPONSORSHIP_PHRASES = [
    'visa sponsorship', 'sponsorship available', 'we sponsor',
    'relocation package', 'relocation support', 'open to international',
    'lmia', 'kennismigrant', 'knowledge migrant', 'ind recognized',
    'skilled worker visa', 'certificate of sponsorship',
    'will sponsor', 'sponsor work permit', 'sponsor visa',
]


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

def load_seen_leads():
    if os.path.exists(LEADS_SEEN_FILE):
        with open(LEADS_SEEN_FILE, 'r') as f:
            return set(json.load(f))
    return set()


def save_seen_leads(seen):
    os.makedirs(os.path.dirname(LEADS_SEEN_FILE), exist_ok=True)
    with open(LEADS_SEEN_FILE, 'w') as f:
        json.dump(list(seen), f)


def fetch_url(url, timeout=15):
    """Fetch a URL with a browser-like user agent."""
    headers = {
        'User-Agent': (
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 '
            '(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36'
        ),
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
    }
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return response.read().decode('utf-8', errors='replace')
    except Exception as e:
        print(f"  [FETCH ERROR] {url}: {e}")
        return ''


def strip_html(html):
    """Remove HTML tags and decode entities."""
    text = re.sub(r'<[^>]+>', ' ', html)
    text = re.sub(r'&amp;', '&', text)
    text = re.sub(r'&lt;', '<', text)
    text = re.sub(r'&gt;', '>', text)
    text = re.sub(r'&nbsp;', ' ', text)
    text = re.sub(r'&quot;', '"', text)
    text = re.sub(r'&#(\d+);', lambda m: chr(int(m.group(1))), text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def is_role_match(title):
    title_lower = title.lower()
    return any(role in title_lower for role in TARGET_ROLES)


def has_dealbreaker(text):
    text_lower = text.lower()
    return any(phrase in text_lower for phrase in DEALBREAKER_PHRASES)


def has_sponsorship_signal(text, country):
    text_lower = text.lower()
    if country == 'United States':
        return any(sig in text_lower for sig in US_SPONSORSHIP_SIGNALS)
    return any(phrase in text_lower for phrase in INTL_SPONSORSHIP_PHRASES)


def skills_match(text):
    text_lower = text.lower()
    matches = sum(1 for skill in CANDIDATE_SKILLS if skill in text_lower)
    return matches >= 2  # at least 2 skill keywords


def write_lead(f, company, title, country, link):
    f.write(f"Company: {company}\n")
    f.write(f"Title: {title}\n")
    f.write(f"Country: {country}\n")
    f.write(f"Link: {link}\n")
    f.write("---\n")


# ─────────────────────────────────────────────
# USAJOBS — United States (Federal)
# ─────────────────────────────────────────────

def search_usajobs():
    """Search USAJobs API for matching roles."""
    print("\n[US] Searching USAJobs.gov...")
    leads = []

    keywords = ['software engineer', 'data engineer', 'full stack developer',
                 'python developer', 'application developer', 'database developer']

    api_base = 'https://data.usajobs.gov/api/search'

    headers_usajobs = {
        'User-Agent': 'mohammad.a.abboud@gmail.com',
        'Authorization-Key': '',  # Public API, no key needed for basic search
        'Host': 'data.usajobs.gov',
    }

    for keyword in keywords:
        url = (
            f"{api_base}?Keyword={urllib.parse.quote(keyword)}"
            f"&ResultsPerPage=25&Fields=Min"
        )
        try:
            req = urllib.request.Request(url, headers=headers_usajobs)
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode('utf-8'))

            items = data.get('SearchResult', {}).get('SearchResultItems', [])
            for item in items:
                desc = item.get('MatchedObjectDescriptor', {})
                title = desc.get('PositionTitle', '')
                company = desc.get('OrganizationName', 'US Federal Government')
                link = desc.get('PositionURI', '') or desc.get('ApplyURI', [''])[0]

                if not title or not link:
                    continue
                if not is_role_match(title):
                    continue

                # USAJobs are government — cap-exempt by nature
                leads.append({
                    'company': company,
                    'title': title,
                    'country': 'United States',
                    'link': link,
                })

        except Exception as e:
            print(f"  USAJobs error for '{keyword}': {e}")

        time.sleep(1)

    print(f"  Found {len(leads)} leads from USAJobs")
    return leads


# ─────────────────────────────────────────────
# TARGET ORGS — US Universities & Nonprofits
# ─────────────────────────────────────────────

def search_target_orgs():
    """Read target-orgs.txt and fetch job listings from each org."""
    print("\n[US] Searching target organizations (universities/nonprofits)...")
    leads = []

    target_orgs_file = os.path.join(os.path.dirname(__file__), '..', 'data', 'target-orgs.txt')
    if not os.path.exists(target_orgs_file):
        print("  target-orgs.txt not found, skipping")
        return leads

    with open(target_orgs_file, 'r') as f:
        lines = [l.strip() for l in f if l.strip() and not l.startswith('#')]

    for url in lines:
        print(f"  Checking: {url}")
        html = fetch_url(url)
        if not html:
            continue

        # Extract job titles and links from career pages
        # Look for anchor tags with job-related text
        pattern = r'href=["\']([^"\']+)["\'][^>]*>([^<]{10,100})</a>'
        matches = re.findall(pattern, html, re.IGNORECASE)

        for href, text in matches:
            text_clean = strip_html(text).strip()
            if not is_role_match(text_clean):
                continue

            # Build absolute URL
            if href.startswith('http'):
                job_url = href
            elif href.startswith('/'):
                parsed = urllib.parse.urlparse(url)
                job_url = f"{parsed.scheme}://{parsed.netloc}{href}"
            else:
                continue

            # Determine company from URL domain
            parsed = urllib.parse.urlparse(url)
            domain = parsed.netloc.replace('www.', '').replace('jobs.', '').replace('careers.', '')
            company = domain.split('.')[0].title()

            leads.append({
                'company': company,
                'title': text_clean,
                'country': 'United States',
                'link': job_url,
            })

        time.sleep(2)

    print(f"  Found {len(leads)} leads from target orgs")
    return leads


# ─────────────────────────────────────────────
# CANADA — Job Bank (Government of Canada)
# ─────────────────────────────────────────────

def search_canada_jobbank():
    """Search Government of Canada Job Bank."""
    print("\n[Canada] Searching Job Bank Canada...")
    leads = []

    keywords = ['software engineer', 'data engineer', 'full stack developer',
                 'python developer', 'application developer']

    for keyword in keywords:
        url = (
            f"https://www.jobbank.gc.ca/jobsearch/jobsearch"
            f"?searchstring={urllib.parse.quote(keyword)}&noc=&fprov=&rtp=1"
        )
        html = fetch_url(url)
        if not html:
            continue

        # Extract job links
        matches = re.findall(
            r'href="(/jobsearch/jobposting/\d+)"[^>]*>.*?<span[^>]*class="[^"]*noctitle[^"]*"[^>]*>([^<]+)',
            html, re.IGNORECASE | re.DOTALL
        )

        for path, title in matches:
            title_clean = title.strip()
            if not is_role_match(title_clean):
                continue

            job_url = f"https://www.jobbank.gc.ca{path}"

            # Fetch individual posting to check for sponsorship + dealbreakers
            time.sleep(1)
            job_html = fetch_url(job_url)
            job_text = strip_html(job_html)

            if has_dealbreaker(job_text):
                continue

            # Try to get company name
            company_match = re.search(
                r'<span[^>]*itemprop="name"[^>]*>([^<]+)</span>', job_html
            )
            company = company_match.group(1).strip() if company_match else 'Canadian Employer'

            # For Canada, if no explicit sponsorship mentioned, check if role is relevant
            if not has_sponsorship_signal(job_text, 'Canada') and not skills_match(job_text):
                continue

            leads.append({
                'company': company,
                'title': title_clean,
                'country': 'Canada',
                'link': job_url,
            })

        time.sleep(2)

    print(f"  Found {len(leads)} leads from Job Bank Canada")
    return leads


# ─────────────────────────────────name──────────
# NETHERLANDS — Indeed NL
# ─────────────────────────────────────────────

def search_indeed_nl():
    """Search Indeed Netherlands for roles with visa sponsorship."""
    print("\n[Netherlands] Searching Indeed NL...")
    leads = []

    search_queries = [
        ('software engineer visa sponsorship', 'Netherlands'),
        ('data engineer visa sponsorship', 'Netherlands'),
        ('full stack developer visa sponsorship', 'Netherlands'),
        ('python developer kennismigrant', 'Netherlands'),
        ('software developer relocation', 'Amsterdam'),
        ('backend developer relocation', 'Netherlands'),
    ]

    for keyword, location in search_queries:
        url = (
            f"https://nl.indeed.com/jobs"
            f"?q={urllib.parse.quote(keyword)}&l={urllib.parse.quote(location)}&limit=25"
        )
        html = fetch_url(url)
        if not html:
            continue

        # Extract job cards
        card_pattern = r'data-jk="([a-z0-9]+)"[^>]*>.*?class="jobTitle"[^>]*><[^>]+>([^<]+)<'
        matches = re.findall(card_pattern, html, re.IGNORECASE | re.DOTALL)

        # Alternative pattern for Indeed job titles
        title_links = re.findall(
            r'href="/viewjob\?jk=([a-z0-9]+)[^"]*"[^>]*>\s*<[^>]*>([^<]{5,80})</[^>]*>',
            html, re.IGNORECASE
        )

        seen_ids = set()
        for job_id, title in title_links:
            title_clean = strip_html(title).strip()
            if not is_role_match(title_clean):
                continue
            if job_id in seen_ids:
                continue
            seen_ids.add(job_id)

            job_url = f"https://nl.indeed.com/viewjob?jk={job_id}"

            # Fetch posting details
            time.sleep(1)
            job_html = fetch_url(job_url)
            job_text = strip_html(job_html)

            if has_dealbreaker(job_text):
                continue
            if not has_sponsorship_signal(job_text, 'Netherlands') and not skills_match(job_text):
                continue

            # Get company
            company_match = re.search(r'"hiringOrganization".*?"name"\s*:\s*"([^"]+)"', job_html)
            company = company_match.group(1) if company_match else 'Dutch Employer'

            leads.append({
                'company': company,
                'title': title_clean,
                'country': 'Netherlands',
                'link': job_url,
            })

        time.sleep(2)

    print(f"  Found {len(leads)} leads from Indeed NL")
    return leads


# ─────────────────────────────────────────────
# SCOTLAND — s1jobs, MyJobScotland, jobs.ac.uk
# ─────────────────────────────────────────────

def search_s1jobs():
    """Search s1jobs.com for Scotland-based tech jobs with sponsorship."""
    print("\n[Scotland] Searching s1jobs.com...")
    leads = []

    keywords = ['software engineer', 'data engineer', 'developer', 'python', 'full stack']

    for keyword in keywords:
        url = (
            f"https://www.s1jobs.com/search-results"
            f"?keywords={urllib.parse.quote(keyword)}&location=Scotland"
        )
        html = fetch_url(url)
        if not html:
            continue

        # Look for job links
        job_links = re.findall(
            r'href="(https://www\.s1jobs\.com/job/[^"]+)"[^>]*>\s*<[^>]*>([^<]{5,100})</[^>]*>',
            html, re.IGNORECASE
        )

        for job_url, title in job_links:
            title_clean = strip_html(title).strip()
            if not is_role_match(title_clean):
                continue

            time.sleep(1)
            job_html = fetch_url(job_url)
            job_text = strip_html(job_html)

            if has_dealbreaker(job_text):
                continue
            if not has_sponsorship_signal(job_text, 'Scotland') and not skills_match(job_text):
                continue

            # Company name
            company_match = re.search(r'<h2[^>]*class="[^"]*employer[^"]*"[^>]*>([^<]+)</h2>', job_html, re.IGNORECASE)
            company = company_match.group(1).strip() if company_match else 'Scottish Employer'

            leads.append({
                'company': company,
                'title': title_clean,
                'country': 'Scotland',
                'link': job_url,
            })

        time.sleep(2)

    print(f"  Found {len(leads)} leads from s1jobs")
    return leads


def search_myjobscotland():
    """Search MyJobScotland.gov.uk (Scottish public sector)."""
    print("\n[Scotland] Searching MyJobScotland (public sector)...")
    leads = []

    keywords = ['software', 'data', 'developer', 'engineer', 'analyst']

    for keyword in keywords:
        url = (
            f"https://www.myjobscotland.gov.uk/jobs"
            f"?keywords={urllib.parse.quote(keyword)}&location=&radius="
        )
        html = fetch_url(url)
        if not html:
            continue

        # Extract job links from public sector listings
        job_links = re.findall(
            r'href="(/jobs/\d+[^"]*)"[^>]*>\s*([^<]{5,100})\s*</a>',
            html, re.IGNORECASE
        )

        for path, title in job_links:
            title_clean = strip_html(title).strip()
            if not is_role_match(title_clean):
                continue

            job_url = f"https://www.myjobscotland.gov.uk{path}"

            time.sleep(1)
            job_html = fetch_url(job_url)
            job_text = strip_html(job_html)

            if has_dealbreaker(job_text):
                continue

            # Public sector often sponsors — include if skills match
            if not skills_match(job_text):
                continue

            # Company = council/org name
            company_match = re.search(r'<h2[^>]*>([^<]+organisation[^<]*)</h2>', job_html, re.IGNORECASE)
            if not company_match:
                company_match = re.search(r'Organisation:\s*</[^>]+>\s*<[^>]+>([^<]+)<', job_html, re.IGNORECASE)
            company = company_match.group(1).strip() if company_match else 'Scottish Public Sector'

            leads.append({
                'company': company,
                'title': title_clean,
                'country': 'Scotland',
                'link': job_url,
            })

        time.sleep(2)

    print(f"  Found {len(leads)} leads from MyJobScotland")
    return leads


def search_jobs_ac_uk():
    """Search jobs.ac.uk for UK university research/tech roles."""
    print("\n[Scotland/UK] Searching jobs.ac.uk (universities & research)...")
    leads = []

    keywords = [
        'software engineer', 'data engineer', 'full stack developer',
        'research software engineer', 'python developer', 'database developer',
    ]

    # jobs.ac.uk lets you filter by region — Scotland region code
    regions = ['Scotland', '']  # Scotland first, then all UK for more results

    for region in regions:
        for keyword in keywords:
            url = (
                f"https://www.jobs.ac.uk/search"
                f"?keywords={urllib.parse.quote(keyword)}"
                f"{'&location=Scotland&radius=0' if region == 'Scotland' else ''}"
            )
            html = fetch_url(url)
            if not html:
                continue

            # Extract job links
            job_links = re.findall(
                r'href="(https://www\.jobs\.ac\.uk/job/[A-Z0-9]+[^"]*)"[^>]*>([^<]{5,100})</a>',
                html, re.IGNORECASE
            )

            for job_url, title in job_links:
                title_clean = strip_html(title).strip()
                if not is_role_match(title_clean):
                    continue

                time.sleep(1)
                job_html = fetch_url(job_url)
                job_text = strip_html(job_html)

                if has_dealbreaker(job_text):
                    continue
                if not skills_match(job_text):
                    continue

                # Determine country
                country = 'Scotland' if region == 'Scotland' else 'United Kingdom'

                # Company
                company_match = re.search(
                    r'<span[^>]*class="[^"]*employer[^"]*"[^>]*>([^<]+)</span>',
                    job_html, re.IGNORECASE
                )
                if not company_match:
                    company_match = re.search(r'<h2[^>]*>([^<]+University[^<]*)</h2>', job_html, re.IGNORECASE)
                company = company_match.group(1).strip() if company_match else 'UK University/Research'

                leads.append({
                    'company': company,
                    'title': title_clean,
                    'country': country,
                    'link': job_url,
                })

            time.sleep(2)

    print(f"  Found {len(leads)} leads from jobs.ac.uk")
    return leads


# ─────────────────────────────────────────────
# WRITE OUTPUT
# ─────────────────────────────────────────────

def write_output(all_leads, seen_urls):
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)

    # Filter out already-seen leads and deduplicate by URL
    new_leads = []
    new_urls = set()
    for lead in all_leads:
        url = lead['link']
        if url not in seen_urls and url not in new_urls:
            new_leads.append(lead)
            new_urls.add(url)

    if not new_leads:
        print("\nNo new leads found this run.")
        return 0

    # Write/append to output file
    file_exists = os.path.exists(OUTPUT_FILE)
    mode = 'a' if file_exists else 'w'

    with open(OUTPUT_FILE, mode) as f:
        if not file_exists:
            f.write("# Job Leads — Mohamad Abboud\n")
            f.write(f"# Last updated: {datetime.now().strftime('%Y-%m-%d')}\n")
            f.write("# Countries: United States, Canada, Netherlands, Scotland\n")
            f.write("# Visa sponsorship required in all\n")
            f.write("#\n\n")
        else:
            f.write(f"\n# Run: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n")

        for lead in new_leads:
            write_lead(f, lead['company'], lead['title'], lead['country'], lead['link'])

    print(f"\nWrote {len(new_leads)} new leads to {OUTPUT_FILE}")
    return len(new_leads)


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

def main():
    print("=" * 60)
    print("JOB FINDER — Mohamad Abboud")
    print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("Countries: US, Canada, Netherlands, Scotland")
    print("=" * 60)

    seen_urls = load_seen_leads()
    all_leads = []

    # United States
    all_leads.extend(search_usajobs())
    all_leads.extend(search_target_orgs())

    # Canada
    all_leads.extend(search_canada_jobbank())

    # Netherlands
    all_leads.extend(search_indeed_nl())

    # Scotland / UK
    all_leads.extend(search_s1jobs())
    all_leads.extend(search_myjobscotland())
    all_leads.extend(search_jobs_ac_uk())

    # Write results
    count = write_output(all_leads, seen_urls)

    # Update seen list
    for lead in all_leads:
        seen_urls.add(lead['link'])
    save_seen_leads(seen_urls)

    print("\n" + "=" * 60)
    print(f"DONE. Total new leads added: {count}")
    print(f"Output: {OUTPUT_FILE}")
    print("=" * 60)


if __name__ == '__main__':
    main()
