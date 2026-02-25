#!/usr/bin/env python3
"""
score.py - Job Matcher & Dealbreaker Detector

Loads raw-jobs.json, checks dealbreakers, scores remaining jobs 1-10,
filters jobs scoring below 6, and saves to data/scored-jobs.json.
"""

import json
import os
import re
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_JOBS_FILE = os.path.join(BASE_DIR, "data", "raw-jobs.json")
SCORED_JOBS_FILE = os.path.join(BASE_DIR, "data", "scored-jobs.json")
APPLICATIONS_FILE = os.path.join(BASE_DIR, "data", "applications.json")
RESUME_FILE = os.path.join(BASE_DIR, "profile", "resume.md")

# Skills from resume
MY_SKILLS = [
    "python", "flask", "c#", "asp.net", ".net", "php",
    "javascript", "vue", "vue.js", "react", "angular", "html", "css", "bootstrap",
    "sql", "postgresql", "postgres", "sql server", "mysql", "t-sql", "stored procedures",
    "rest api", "restful", "git", "docker", "ci/cd", "agile", "scrum",
    "etl", "data modeling", "data model",
    "node", "typescript",
]

DEALBREAKER_PATTERNS = [
    r"no sponsorship",
    r"unable to sponsor",
    r"cannot sponsor",
    r"will not sponsor",
    r"does not sponsor",
    r"authorized to work without sponsorship",
    r"must be authorized to work",
    r"without the need for sponsorship",
    r"must be (a )?(us|u\.s\.) citizen",
    r"(us|u\.s\.) citizenship required",
    r"permanent resident(s)? (only|required)",
    r"green card (only|required|holder)",
    r"security clearance required",
    r"top secret",
    r"secret clearance",
]

DEALBREAKER_EMPLOYERS = [
    r"credit union",
    r"k-12",
    r"school district",
    r"elementary school",
    r"middle school",
    r"high school",
]

SENIOR_PATTERNS = [
    r"\b(10|eleven|twelve|\d{2})\+?\s+years?\s+(of\s+)?experience",
    r"\bprincipal\s+(software|engineer|developer)",
    r"\bstaff\s+(software|engineer|developer)",
    r"\bdistinguished\s+(software|engineer|developer)",
]

CAP_EXEMPT_SIGNALS = [
    "university", "college", "institute of technology",
    "hospital", "health system", "medical center",
    "nonprofit", "non-profit", "foundation",
    "research institute", "national lab",
    "department of", ".gov", ".edu",
]


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


def has_dealbreaker(job: dict) -> tuple[bool, str]:
    """Return (True, reason) if the job has a dealbreaker, else (False, '')."""
    text = (job.get("description", "") + " " + job.get("title", "")).lower()
    url = job.get("url", "").lower()
    combined = text + " " + url

    for pat in DEALBREAKER_PATTERNS:
        if re.search(pat, combined):
            return True, f"Dealbreaker phrase: {pat}"

    for pat in DEALBREAKER_EMPLOYERS:
        if re.search(pat, combined):
            return True, f"Non-cap-exempt employer: {pat}"

    for pat in SENIOR_PATTERNS:
        if re.search(pat, combined):
            return True, f"Over-leveled: {pat}"

    return False, ""


def score_job(job: dict) -> tuple[float, list]:
    """Score a job 1-10. Returns (score, reasons)."""
    score = 0.0
    reasons = []
    text = (job.get("description", "") + " " + job.get("title", "")).lower()
    url = (job.get("url", "") + " " + job.get("company", "")).lower()
    combined = text + " " + url

    # Cap-exempt status: +3
    cap_exempt = job.get("cap_exempt_likely", False)
    if not cap_exempt:
        cap_exempt = any(sig in combined for sig in CAP_EXEMPT_SIGNALS)
    if cap_exempt:
        score += 3
        reasons.append("+3 cap-exempt employer")

    # Skills match: 0-4 points
    matched_skills = [skill for skill in MY_SKILLS if skill in combined]
    skill_score = min(4.0, len(matched_skills) * 0.5)
    score += skill_score
    if matched_skills:
        reasons.append(f"+{skill_score:.1f} skills match ({', '.join(matched_skills[:5])})")

    # Experience level match: 0-2 points
    exp_match = re.search(r"(\d+)[\+\s]*years?\s+(of\s+)?experience", text)
    if exp_match:
        years = int(exp_match.group(1))
        if 2 <= years <= 7:
            score += 2
            reasons.append(f"+2 experience level match ({years} yrs)")
        elif years <= 9:
            score += 1
            reasons.append(f"+1 experience level ok ({years} yrs)")
        else:
            score -= 1
            reasons.append(f"-1 too senior ({years} yrs)")
    else:
        score += 1
        reasons.append("+1 no specific experience requirement stated")

    # Salary: +1 if listed and >= 70k
    salary = job.get("salary", "")
    if salary:
        nums = re.findall(r"[\d,]+", salary.replace(",", ""))
        if nums:
            try:
                val = int(nums[0])
                if val < 1000:
                    val *= 1000  # handle "80k"
                if val >= 70000:
                    score += 1
                    reasons.append(f"+1 salary listed and ≥$70k ({salary})")
                else:
                    score -= 1
                    reasons.append(f"-1 salary below $70k ({salary})")
            except ValueError:
                pass

    return round(min(10.0, max(1.0, score)), 1), reasons


def main():
    print("=== Phase 2: Dealbreaker Check & Scoring ===", flush=True)

    raw_jobs = load_json(RAW_JOBS_FILE)
    if not raw_jobs:
        print("[WARN] No jobs found in raw-jobs.json. Run search.py first.")
        return 0

    existing_apps = load_json(APPLICATIONS_FILE)
    applied_urls = {a.get("url", "") for a in existing_apps}

    existing_scored = load_json(SCORED_JOBS_FILE)
    scored_urls = {j["url"] for j in existing_scored}

    results = list(existing_scored)

    skipped = 0
    scored_count = 0
    passed = 0

    for job in raw_jobs:
        url = job.get("url", "")

        # Skip already applied
        if url in applied_urls:
            print(f"  SKIP (already applied): {job.get('title')} @ {job.get('company')}")
            skipped += 1
            continue

        # Skip already scored
        if url in scored_urls:
            continue

        title = job.get("title", "?")
        company = job.get("company", "?")

        # Check dealbreakers first
        is_deal, reason = has_dealbreaker(job)
        if is_deal:
            print(f"  SKIP [{reason}]: {title} @ {company}")
            results.append({**job, "score": 0, "status": "skipped", "skip_reason": reason, "score_reasons": []})
            skipped += 1
            continue

        # Score the job
        score, reasons = score_job(job)
        scored_count += 1

        if score < 6:
            print(f"  LOW SCORE ({score}): {title} @ {company} -> filtered out")
            results.append({**job, "score": score, "status": "filtered", "skip_reason": f"Score {score} < 6", "score_reasons": reasons})
        else:
            print(f"  PASS ({score}/10): {title} @ {company} | {' | '.join(reasons)}")
            results.append({**job, "score": score, "status": "qualified", "skip_reason": "", "score_reasons": reasons})
            passed += 1

    with open(SCORED_JOBS_FILE, "w") as f:
        json.dump(results, f, indent=2)

    print(f"\n[DONE] Scored {scored_count} job(s). {passed} qualified (score ≥ 6). {skipped} skipped.")
    print(f"       Results saved to data/scored-jobs.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
