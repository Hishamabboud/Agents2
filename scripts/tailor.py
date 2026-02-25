#!/usr/bin/env python3
"""
tailor.py - Resume & Cover Letter Generator

For each qualified job in scored-jobs.json, generates a tailored resume and
cover letter. Saves both into a single per-job directory:
  output/applications/{app_id}/resume.md
  output/applications/{app_id}/cover-letter.md

App ID format: YYYYMMDD_{state}_{company-slug}_{role-slug}
  e.g. 20260225_CA_stanford_python-developer
"""

import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCORED_JOBS_FILE = os.path.join(BASE_DIR, "data", "scored-jobs.json")
RESUME_FILE = os.path.join(BASE_DIR, "profile", "resume.md")
COVER_LETTER_TEMPLATE_FILE = os.path.join(BASE_DIR, "profile", "cover-letter-template.md")
APPLICATIONS_OUTPUT_DIR = os.path.join(BASE_DIR, "output", "applications")

# State abbreviation lookup (city/region hints → state code)
STATE_HINTS = {
    "montana": "MT", "mt": "MT", "missoula": "MT", "bozeman": "MT", "billings": "MT", "helena": "MT",
    "california": "CA", "ca": "CA", "stanford": "CA", "berkeley": "CA", "los angeles": "CA",
    "san francisco": "CA", "san diego": "CA", "sacramento": "CA", "pasadena": "CA",
    "missouri": "MO", "mo": "MO", "columbia": "MO", "st. louis": "MO", "st louis": "MO",
    "kansas city": "MO",
    "kansas": "KS", "ks": "KS", "lawrence": "KS", "manhattan": "KS", "wichita": "KS",
    "tennessee": "TN", "tn": "TN", "nashville": "TN", "knoxville": "TN", "memphis": "TN",
    "colorado": "CO", "co": "CO", "denver": "CO", "boulder": "CO", "fort collins": "CO",
    "aurora": "CO",
    "maryland": "MD", "md": "MD", "baltimore": "MD", "bethesda": "MD",
    "michigan": "MI", "mi": "MI", "ann arbor": "MI",
    "minnesota": "MN", "mn": "MN", "rochester": "MN", "st. paul": "MN", "minneapolis": "MN",
    "new york": "NY", "ny": "NY",
    "washington": "WA", "wa": "WA", "seattle": "WA",
    "massachusetts": "MA", "ma": "MA", "boston": "MA", "cambridge": "MA",
    "illinois": "IL", "il": "IL", "chicago": "IL",
    "texas": "TX", "tx": "TX", "austin": "TX", "houston": "TX", "dallas": "TX",
    "remote": "REMOTE",
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


def read_file(path: str) -> str:
    try:
        with open(path) as f:
            return f.read()
    except IOError:
        return ""


def slugify(text: str, max_len: int = 30) -> str:
    """Convert text to a URL/filesystem-safe slug."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"-+", "-", text).strip("-")
    return text[:max_len]


def detect_state(location: str, url: str) -> str:
    """Detect US state from job location string or URL."""
    combined = (location + " " + url).lower()
    for hint, code in STATE_HINTS.items():
        if hint in combined:
            return code
    return "USA"


def make_app_id(job: dict) -> str:
    """
    Build a unique application directory ID:
    YYYYMMDD_{STATE}_{company-slug}_{role-slug}
    """
    date_str = datetime.now().strftime("%Y%m%d")
    state = detect_state(job.get("location", ""), job.get("url", ""))
    company_slug = slugify(job.get("company", "unknown"), max_len=20)
    role_slug = slugify(job.get("title", "role"), max_len=25)
    return f"{date_str}_{state}_{company_slug}_{role_slug}"


def call_claude(prompt: str) -> str:
    """
    Call Claude via claude CLI subprocess.
    Falls back to Anthropic Python SDK if CLI unavailable.
    """
    try:
        result = subprocess.run(
            ["claude", "-p", prompt],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    try:
        import anthropic
        client = anthropic.Anthropic()
        message = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2048,
            messages=[{"role": "user", "content": prompt}],
        )
        return message.content[0].text
    except Exception as e:
        print(f"  [ERROR] Claude unavailable: {e}", file=sys.stderr)
        return ""


def generate_tailored_resume(job: dict, resume: str) -> str:
    job_desc = job.get("description", "")[:3000]
    title = job.get("title", "")
    company = job.get("company", "")

    prompt = f"""You are a professional resume writer. Tailor the following resume for this specific job posting.

JOB TITLE: {title}
COMPANY: {company}
JOB DESCRIPTION (excerpt):
{job_desc}

ORIGINAL RESUME:
{resume}

INSTRUCTIONS:
1. Mirror EXACT keywords from the job description for ATS optimization
2. Reorder the Technical Skills section to match the job's requirements first
3. Adjust bullet points to emphasize the most relevant experience
4. Keep the resume to ONE PAGE maximum (~400 words)
5. Do NOT fabricate any experience, skills, or qualifications not in the original
6. Do NOT mention H-1B, visa status, or sponsorship
7. Keep Mohamad's real contact info and education unchanged
8. Output ONLY the tailored resume in markdown, no commentary

OUTPUT: A tailored resume in markdown format."""
    return call_claude(prompt)


def generate_cover_letter(job: dict, resume: str, template: str) -> str:
    job_desc = job.get("description", "")[:3000]
    title = job.get("title", "")
    company = job.get("company", "")
    url = job.get("url", "")

    is_healthcare = any(
        kw in (job_desc + company + title).lower()
        for kw in ["hospital", "health", "medical", "clinic", "patient", "clinical"]
    )

    prompt = f"""You are writing a personalized cover letter for Mohamad Abboud.

JOB TITLE: {title}
COMPANY/ORG: {company}
JOB URL: {url}
JOB DESCRIPTION (excerpt):
{job_desc}

CANDIDATE'S RESUME:
{resume}

COVER LETTER TEMPLATE/GUIDELINES:
{template}

INSTRUCTIONS:
1. Write a 500-600 word cover letter in simple, human language
2. NO corporate jargon - write like a real person
3. Connect authentically to the organization's mission
4. Mirror exact keywords from the job description
5. Reference relevant projects: KCD EDI system, KidsCloset acquisition, KC Sports Directory, College Basketball Experience
6. Mention C#/ASP.NET and SQL Server work for 400+ banking clients if relevant
{"7. Mention brother is a physician and sister is a psychologist - genuine healthcare passion" if is_healthcare else ""}
8. Do NOT mention H-1B, visa status, OPT, or sponsorship
9. End with: Best regards, Mohamad Abboud
10. Output ONLY the cover letter, no commentary

OUTPUT: The complete cover letter."""
    return call_claude(prompt)


def main():
    print("=== Phase 3: Resume & Cover Letter Generation ===", flush=True)
    print(f"Output directory: output/applications/{{app_id}}/", flush=True)

    scored_jobs = load_json(SCORED_JOBS_FILE)
    qualified = [j for j in scored_jobs if j.get("status") == "qualified"]

    if not qualified:
        print("[WARN] No qualified jobs found. Run score.py first.")
        return 0

    resume = read_file(RESUME_FILE)
    template = read_file(COVER_LETTER_TEMPLATE_FILE)

    if not resume:
        print("[ERROR] Could not read profile/resume.md")
        return 1

    Path(APPLICATIONS_OUTPUT_DIR).mkdir(parents=True, exist_ok=True)
    generated = 0

    for i, job in enumerate(scored_jobs):
        if job.get("status") != "qualified":
            continue

        title = job.get("title", "unknown")
        company = job.get("company", "unknown")

        # Use existing app_id if already assigned, otherwise generate one
        app_id = job.get("app_id") or make_app_id(job)
        app_dir = os.path.join(APPLICATIONS_OUTPUT_DIR, app_id)
        resume_path = os.path.join(app_dir, "resume.md")
        cover_letter_path = os.path.join(app_dir, "cover-letter.md")

        # Skip if both files already exist
        if os.path.exists(resume_path) and os.path.exists(cover_letter_path):
            print(f"  SKIP (already generated): [{app_id}] {title} @ {company}")
            scored_jobs[i]["app_id"] = app_id
            scored_jobs[i]["app_dir"] = app_dir
            scored_jobs[i]["resume_file"] = resume_path
            scored_jobs[i]["cover_letter_file"] = cover_letter_path
            continue

        print(f"\n  [{app_id}]")
        print(f"  {title} @ {company} (score: {job.get('score')})")
        Path(app_dir).mkdir(parents=True, exist_ok=True)

        # Generate tailored resume
        print("    -> Tailoring resume ...", flush=True)
        tailored_resume = generate_tailored_resume(job, resume)
        if not tailored_resume:
            print(f"    [ERROR] Failed to generate resume")
            continue

        with open(resume_path, "w") as f:
            f.write(tailored_resume)
        print(f"    -> resume.md saved")

        # Generate cover letter
        print("    -> Writing cover letter ...", flush=True)
        cover_letter = generate_cover_letter(job, resume, template)
        if not cover_letter:
            print(f"    [ERROR] Failed to generate cover letter")
            continue

        with open(cover_letter_path, "w") as f:
            f.write(cover_letter)
        print(f"    -> cover-letter.md saved")

        scored_jobs[i]["app_id"] = app_id
        scored_jobs[i]["app_dir"] = app_dir
        scored_jobs[i]["resume_file"] = resume_path
        scored_jobs[i]["cover_letter_file"] = cover_letter_path
        generated += 1

        if i < len(scored_jobs) - 1:
            time.sleep(3)

    # Save updated records
    with open(SCORED_JOBS_FILE, "w") as f:
        json.dump(scored_jobs, f, indent=2)

    print(f"\n[DONE] Generated materials for {generated} job(s).")
    print(f"       Application packages in: output/applications/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
