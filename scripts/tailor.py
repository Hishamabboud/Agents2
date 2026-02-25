#!/usr/bin/env python3
"""
tailor.py - Resume & Cover Letter Generator

For each qualified job in scored-jobs.json, generates a tailored resume
and cover letter using Claude (via subprocess claude CLI or Anthropic API).
Saves to output/tailored-resumes/ and output/cover-letters/.
"""

import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCORED_JOBS_FILE = os.path.join(BASE_DIR, "data", "scored-jobs.json")
RESUME_FILE = os.path.join(BASE_DIR, "profile", "resume.md")
COVER_LETTER_TEMPLATE_FILE = os.path.join(BASE_DIR, "profile", "cover-letter-template.md")
PREFERENCES_FILE = os.path.join(BASE_DIR, "profile", "preferences.md")
RESUME_OUTPUT_DIR = os.path.join(BASE_DIR, "output", "tailored-resumes")
COVER_LETTER_OUTPUT_DIR = os.path.join(BASE_DIR, "output", "cover-letters")


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


def safe_filename(company: str, title: str) -> str:
    """Create a safe filename from company and title."""
    name = f"{company}-{title}"
    name = re.sub(r"[^\w\s-]", "", name)
    name = re.sub(r"\s+", "-", name.strip())
    return name[:80].lower()


def call_claude(prompt: str) -> str:
    """
    Call Claude via the claude CLI subprocess.
    Falls back to Anthropic Python SDK if CLI unavailable.
    """
    # Try claude CLI first
    try:
        result = subprocess.run(
            ["claude", "-p", prompt],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
        print(f"  [WARN] claude CLI returned code {result.returncode}", file=sys.stderr)
        if result.stderr:
            print(f"  [WARN] stderr: {result.stderr[:200]}", file=sys.stderr)
    except (FileNotFoundError, subprocess.TimeoutExpired) as e:
        print(f"  [WARN] claude CLI error: {e}", file=sys.stderr)

    # Fallback: Anthropic Python SDK
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
        print(f"  [ERROR] Anthropic SDK also failed: {e}", file=sys.stderr)
        return ""


def generate_tailored_resume(job: dict, resume: str) -> str:
    """Generate a tailored resume for the given job."""
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
    """Generate a tailored cover letter for the given job."""
    job_desc = job.get("description", "")[:3000]
    title = job.get("title", "")
    company = job.get("company", "")
    url = job.get("url", "")

    # Detect if healthcare-related
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
{f"7. Mention brother is a physician and sister is a psychologist - genuine healthcare passion" if is_healthcare else ""}
8. Do NOT mention H-1B, visa status, OPT, or sponsorship
9. End with: Best regards, Mohamad Abboud
10. Output ONLY the cover letter, no commentary

OUTPUT: The complete cover letter."""

    return call_claude(prompt)


def update_scored_jobs(scored_jobs: list) -> None:
    """Write updated scored jobs back to file."""
    with open(SCORED_JOBS_FILE, "w") as f:
        json.dump(scored_jobs, f, indent=2)


def main():
    print("=== Phase 3: Resume & Cover Letter Generation ===", flush=True)

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

    Path(RESUME_OUTPUT_DIR).mkdir(parents=True, exist_ok=True)
    Path(COVER_LETTER_OUTPUT_DIR).mkdir(parents=True, exist_ok=True)

    generated = 0

    for i, job in enumerate(scored_jobs):
        if job.get("status") != "qualified":
            continue

        title = job.get("title", "unknown")
        company = job.get("company", "unknown")
        fname = safe_filename(company, title)

        resume_path = os.path.join(RESUME_OUTPUT_DIR, f"{fname}.md")
        cover_letter_path = os.path.join(COVER_LETTER_OUTPUT_DIR, f"{fname}.md")

        # Skip if already generated
        if os.path.exists(resume_path) and os.path.exists(cover_letter_path):
            print(f"  SKIP (already generated): {title} @ {company}")
            # Make sure file paths are recorded
            scored_jobs[i]["resume_file"] = resume_path
            scored_jobs[i]["cover_letter_file"] = cover_letter_path
            continue

        print(f"\n  Generating materials for: {title} @ {company} (score: {job.get('score')})")

        # Generate tailored resume
        print("    -> Tailoring resume ...", flush=True)
        tailored_resume = generate_tailored_resume(job, resume)
        if not tailored_resume:
            print(f"    [ERROR] Failed to generate resume for {title} @ {company}")
            continue

        with open(resume_path, "w") as f:
            f.write(tailored_resume)
        print(f"    -> Resume saved: {resume_path}")

        # Generate cover letter
        print("    -> Writing cover letter ...", flush=True)
        cover_letter = generate_cover_letter(job, resume, template)
        if not cover_letter:
            print(f"    [ERROR] Failed to generate cover letter for {title} @ {company}")
            continue

        with open(cover_letter_path, "w") as f:
            f.write(cover_letter)
        print(f"    -> Cover letter saved: {cover_letter_path}")

        # Update the job record with file paths
        scored_jobs[i]["resume_file"] = resume_path
        scored_jobs[i]["cover_letter_file"] = cover_letter_path
        generated += 1

        # Rate-limit between Claude calls
        if i < len(scored_jobs) - 1:
            time.sleep(5)

    # Save updated records
    update_scored_jobs(scored_jobs)

    print(f"\n[DONE] Generated materials for {generated} job(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
