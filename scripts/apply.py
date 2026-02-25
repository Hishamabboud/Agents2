#!/usr/bin/env python3
"""
apply.py - Application Submitter

Uses Playwright (if available via MCP or local install) to automate form filling.
Handles common ATS platforms: Workday, Greenhouse, Lever, Taleo, iCIMS.
Falls back to logging "manual_required" if browser automation is unavailable.
"""

import json
import os
import re
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCORED_JOBS_FILE = os.path.join(BASE_DIR, "data", "scored-jobs.json")
APPLICATIONS_FILE = os.path.join(BASE_DIR, "data", "applications.json")
APPLICATIONS_OUTPUT_DIR = os.path.join(BASE_DIR, "output", "applications")

# Candidate details from preferences.md
CANDIDATE = {
    "full_name": "Mohamad Abboud",
    "first_name": "Mohamad",
    "last_name": "Abboud",
    "email": "mohammad.a.abboud@gmail.com",
    "phone": "(406) 920-5162",
    "location": "St. Paul, Minnesota",
    "city": "St. Paul",
    "state": "MN",
    "zip": "55101",
    "linkedin": "",
    "github": "https://github.com/MoAbboud",
    "years_experience": "5",
    "salary_expectation": "85000",
    "authorized_to_work": "Yes",
    "requires_sponsorship": "Yes",
    "willing_to_relocate": "Yes",
}


def load_json(path: str, default=None):
    if default is None:
        default = []
    if not os.path.exists(path):
        return default
    try:
        with open(path) as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return default


def detect_ats(url: str) -> str:
    """Detect the ATS platform from the URL."""
    url_lower = url.lower()
    if "greenhouse.io" in url_lower or "boards.greenhouse" in url_lower:
        return "greenhouse"
    if "workday.com" in url_lower or "myworkdayjobs.com" in url_lower:
        return "workday"
    if "lever.co" in url_lower:
        return "lever"
    if "taleo.net" in url_lower:
        return "taleo"
    if "icims.com" in url_lower:
        return "icims"
    if "successfactors" in url_lower:
        return "successfactors"
    if "usajobs.gov" in url_lower:
        return "usajobs"
    return "unknown"


def read_file(path: str) -> str:
    if not path or not os.path.exists(path):
        return ""
    try:
        with open(path) as f:
            return f.read()
    except IOError:
        return ""


def check_playwright_available() -> bool:
    """Check if Playwright is importable (local install)."""
    try:
        import playwright  # noqa: F401
        return True
    except ImportError:
        return False


def apply_via_playwright(job: dict) -> dict:
    """
    Attempt to apply using Playwright browser automation.
    Returns result dict with status and notes.
    """
    url = job.get("url", "")
    ats = detect_ats(url)
    resume_file = job.get("resume_file", "")
    cover_letter_file = job.get("cover_letter_file", "")
    cover_letter_text = read_file(cover_letter_file)

    # Screenshot goes into the per-job app directory
    app_dir = job.get("app_dir", os.path.join(APPLICATIONS_OUTPUT_DIR, job.get("app_id", "unknown")))
    Path(app_dir).mkdir(parents=True, exist_ok=True)
    screenshot_path = os.path.join(app_dir, "screenshot.png")

    try:
        from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context()
            page = context.new_page()

            print(f"    -> Navigating to {url} (ATS: {ats})")
            page.goto(url, timeout=30000)
            page.wait_for_load_state("networkidle", timeout=15000)

            # Screenshot the application page
            page.screenshot(path=screenshot_path)
            print(f"    -> Screenshot: {screenshot_path}")

            # Generic form filling strategy
            filled_fields = []

            # Fill name fields
            for selector in ['input[name*="first"][type="text"]', 'input[placeholder*="First"]',
                              'input[id*="first_name"]', 'input[id*="firstName"]']:
                try:
                    el = page.locator(selector).first
                    if el.is_visible():
                        el.fill(CANDIDATE["first_name"])
                        filled_fields.append("first_name")
                        break
                except Exception:
                    pass

            for selector in ['input[name*="last"][type="text"]', 'input[placeholder*="Last"]',
                              'input[id*="last_name"]', 'input[id*="lastName"]']:
                try:
                    el = page.locator(selector).first
                    if el.is_visible():
                        el.fill(CANDIDATE["last_name"])
                        filled_fields.append("last_name")
                        break
                except Exception:
                    pass

            # Email
            for selector in ['input[type="email"]', 'input[name*="email"]', 'input[id*="email"]']:
                try:
                    el = page.locator(selector).first
                    if el.is_visible():
                        el.fill(CANDIDATE["email"])
                        filled_fields.append("email")
                        break
                except Exception:
                    pass

            # Phone
            for selector in ['input[type="tel"]', 'input[name*="phone"]', 'input[id*="phone"]']:
                try:
                    el = page.locator(selector).first
                    if el.is_visible():
                        el.fill(CANDIDATE["phone"])
                        filled_fields.append("phone")
                        break
                except Exception:
                    pass

            # Resume upload
            if resume_file and os.path.exists(resume_file):
                for selector in ['input[type="file"]']:
                    try:
                        el = page.locator(selector).first
                        if el.is_visible(timeout=2000) or True:
                            el.set_input_files(resume_file)
                            filled_fields.append("resume_upload")
                            break
                    except Exception:
                        pass

            # Cover letter textarea
            if cover_letter_text:
                for selector in ['textarea[name*="cover"]', 'textarea[id*="cover"]',
                                  'textarea[placeholder*="cover"]', 'textarea']:
                    try:
                        el = page.locator(selector).first
                        if el.is_visible():
                            el.fill(cover_letter_text[:5000])
                            filled_fields.append("cover_letter")
                            break
                    except Exception:
                        pass

            # Final screenshot before submit
            page.screenshot(path=screenshot_path)
            print(f"    -> Pre-submit screenshot saved: {screenshot_path}")
            print(f"    -> Filled fields: {filled_fields}")

            # NOTE: We do NOT auto-submit unless explicitly enabled.
            # This is a safety measure to prevent unintended applications.
            print("    -> [SAFETY] Auto-submit is DISABLED. Review the application manually.")
            print(f"    -> Application URL: {url}")

            browser.close()

        return {
            "status": "ready_to_submit",
            "screenshot": screenshot_path,
            "filled_fields": filled_fields,
            "notes": "Form pre-filled. Manual review required before submission.",
        }

    except ImportError:
        return {
            "status": "manual_required",
            "screenshot": "",
            "notes": "Playwright not installed. Apply manually.",
        }
    except Exception as e:
        return {
            "status": "failed",
            "screenshot": screenshot_path if os.path.exists(screenshot_path) else "",
            "notes": f"Error during automation: {str(e)[:200]}",
        }


def log_application(job: dict, apply_result: dict) -> None:
    """Append a new application record to applications.json."""
    apps = load_json(APPLICATIONS_FILE)

    # Avoid duplicates
    existing_urls = {a.get("url", "") for a in apps}
    if job.get("url", "") in existing_urls:
        return

    app_id = job.get("app_id", "")
    app_dir = job.get("app_dir", apply_result.get("app_dir", ""))
    record = {
        "id": str(uuid.uuid4()),
        "app_id": app_id,
        "app_dir": app_dir,
        "company": job.get("company", ""),
        "role": job.get("title", ""),
        "url": job.get("url", ""),
        "cap_exempt": job.get("cap_exempt_likely", False),
        "salary": job.get("salary", ""),
        "date_applied": datetime.now().strftime("%Y-%m-%d"),
        "score": job.get("score", 0),
        "status": apply_result.get("status", "unknown"),
        "materials": f"output/applications/{app_id}/" if app_id else "",
        "screenshot": apply_result.get("screenshot", ""),
        "notes": apply_result.get("notes", ""),
        "response": "pending",
    }
    apps.append(record)

    with open(APPLICATIONS_FILE, "w") as f:
        json.dump(apps, f, indent=2)


def main():
    print("=== Phase 4: Application Submission ===", flush=True)

    scored_jobs = load_json(SCORED_JOBS_FILE)
    apps = load_json(APPLICATIONS_FILE)
    applied_urls = {a.get("url", "") for a in apps}

    # Only process qualified jobs that have tailored materials
    to_apply = [
        j for j in scored_jobs
        if j.get("status") == "qualified"
        and j.get("url", "") not in applied_urls
        and j.get("resume_file", "")
        and os.path.exists(j.get("resume_file", ""))
    ]

    if not to_apply:
        print("[WARN] No qualified jobs ready to apply. Run tailor.py first.")
        return 0

    has_playwright = check_playwright_available()
    if not has_playwright:
        print("[INFO] Playwright not installed locally. Will log as manual_required.")
        print("[INFO] Install with: pip install playwright && playwright install chromium")

    for job in to_apply:
        title = job.get("title", "?")
        company = job.get("company", "?")
        url = job.get("url", "")
        ats = detect_ats(url)

        print(f"\n  Applying to: {title} @ {company}")
        print(f"  URL: {url}")
        print(f"  ATS: {ats}")
        print(f"  Score: {job.get('score')}")

        app_id = job.get("app_id", "unknown")
        app_dir = job.get("app_dir", os.path.join(APPLICATIONS_OUTPUT_DIR, app_id))

        if has_playwright:
            result = apply_via_playwright(job)
        else:
            result = {
                "status": "manual_required",
                "screenshot": "",
                "app_dir": app_dir,
                "notes": (
                    f"Playwright not available. Apply manually at: {url}. "
                    f"Materials in: output/applications/{app_id}/"
                ),
            }

        print(f"  Result: {result['status']}")
        if result.get("notes"):
            print(f"  Notes: {result['notes']}")

        log_application(job, result)
        print(f"  Logged to applications.json")

        # Rate limiting
        time.sleep(5)

    total = len(to_apply)
    print(f"\n[DONE] Processed {total} application(s). Check data/applications.json for details.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
