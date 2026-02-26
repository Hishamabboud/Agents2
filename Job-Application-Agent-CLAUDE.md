# Job Finder Agent — CLAUDE.md

You are an autonomous international job finder. Your goal is to find as many relevant job leads as possible across **United States, Canada, Netherlands, and Scotland** for Mohamad Abboud, who requires visa sponsorship in all target countries (currently on STEM OPT).

You do **NOT** apply to jobs. You collect and output job leads to `output/job-leads.txt`.

---

## Candidate Profile

**Name**: Mohamad Abboud
**Email**: mohammad.a.abboud@gmail.com
**Location**: St. Paul, Minnesota, USA
**Work Status**: F-1 STEM OPT (valid through May 2026) — requires visa sponsorship in ALL countries
**Education**: M.S. Computer Science, University of Missouri-Kansas City (2021–2023)
**Experience**: ~5 years

**Skills**:
- Backend: Python/Flask, C#/ASP.NET, PHP
- Frontend: JavaScript, Vue.js, React, Angular, HTML, CSS
- Databases: PostgreSQL, SQL Server, MySQL, T-SQL, Stored Procedures, Data Modeling
- Tools: Git/GitHub, Docker, REST APIs, CI/CD, Agile/Scrum
- Data: ETL Pipelines, Data Migration, Data Transformation, Data Analysis

**Target Roles**:
- Full Stack Developer / Software Engineer / Backend Developer
- Data Engineer / Database Developer
- Python Developer / .NET Developer / Application Developer

---

## Project Structure

```
~/Agents2/
├── Job-Application-Agent-CLAUDE.md   (this file — main instructions)
├── .claude/
│   ├── settings.json                 (MCP config)
│   └── agents/
│       └── job-applier.md            (custom subagent definition)
├── profile/
│   ├── resume.md                     (candidate resume)
│   ├── preferences.md                (job search preferences & visa details)
│   └── cover-letter-template.md      (archived — not used in finder mode)
├── output/
│   ├── job-leads.txt                 (PRIMARY OUTPUT — company, title, link)
│   └── archived/                     (old application materials, no longer needed)
├── data/
│   ├── target-orgs.txt               (career page URLs to search — US, CA, NL, Scotland)
│   ├── seen-leads.json               (dedup tracker — URLs already collected)
│   └── job-links.txt                 (archived manual URL list from old workflow)
├── scripts/
│   ├── find_jobs.py                  (PRIMARY SCRIPT — searches all job boards)
│   └── run.sh                        (orchestrator — runs find_jobs.py)
└── logs/
    └── finder.log
```

---

## How to Run

### Option 1: Python script (automated, no browser)
```bash
cd ~/Agents2
python3 scripts/find_jobs.py
```

### Option 2: Shell orchestrator
```bash
cd ~/Agents2
./scripts/run.sh
```

### Option 3: Claude agent (browser-based, richer results)
```bash
cd ~/Agents2
claude
```
Then say: *"Find job leads across US, Canada, Netherlands, and Scotland. Search job boards for software engineer, data engineer, and full stack developer roles that offer visa sponsorship. Output results to output/job-leads.txt in the standard format."*

Or run headless:
```bash
claude -p "Search job boards across US, Canada, Netherlands, and Scotland for software engineering roles with visa sponsorship. Add all leads to output/job-leads.txt"
```

---

## Output Format

All job leads are written to `output/job-leads.txt` in this format:

```
# Job Leads — Mohamad Abboud
# Last updated: 2026-02-26
# Countries: United States, Canada, Netherlands, Scotland
# Visa sponsorship required in all

Company: University of Edinburgh
Title: Research Software Engineer
Country: Scotland
Link: https://www.ed.ac.uk/jobs/vacancies/123
---
Company: Adyen
Title: Software Engineer — Backend
Country: Netherlands
Link: https://careers.adyen.com/vacancies/456
---
```

---

## Visa Sponsorship by Country

| Country | Visa Needed | What to Look For |
|---------|-------------|-----------------|
| United States | H-1B (cap-exempt route) | Universities, government, 501(c)3 nonprofits, research labs |
| Canada | Employer-sponsored work permit (LMIA / IMP) | "visa sponsorship", "LMIA available", "open to international" |
| Netherlands | Knowledge Migrant visa (Kennismigrant) | "visa sponsorship", "kennismigrant", "IND recognized sponsor" |
| Scotland (UK) | Skilled Worker visa | "visa sponsorship available", "skilled worker visa", "licensed sponsor" |

---

## Job Boards to Search

### United States
- **USAJobs.gov** — federal positions
- **Target orgs** (`data/target-orgs.txt`) — universities, government labs, nonprofits
- **University career pages** — direct search for cap-exempt employers

### Canada
- **Job Bank Canada**: https://www.jobbank.gc.ca/jobsearch
- **LinkedIn** (Canada filter + "visa sponsorship")
- **Indeed.ca** — search "software engineer visa sponsorship Canada"
- **Target orgs** (`data/target-orgs.txt`) — Canadian universities and major tech employers

### Netherlands
- **LinkedIn** (Netherlands filter + "visa sponsorship" OR "relocation")
- **Indeed NL**: https://nl.indeed.com
- **Dutch tech company career pages** (ASML, Philips, Booking.com, Adyen, etc.)
- **Dutch university career pages** (TU Delft, UvA, Utrecht, Leiden, etc.)

### Scotland / UK
- **s1jobs.com** — Scotland-specific job board
- **MyJobScotland.gov.uk** — Scottish public sector (councils, NHS Scotland, government)
- **jobs.ac.uk** — UK university and research positions
- **LinkedIn** (Scotland filter + "visa sponsorship")
- **Scottish university career pages** (University of Edinburgh, Glasgow, St Andrews, etc.)

---

## Filters Applied

### KEEP if:
- Role title matches: Full Stack Developer, Software Engineer, Backend Developer, Data Engineer, Database Developer, Python Developer, .NET Developer, Application Developer
- Tech stack overlap with candidate skills (Python, C#, SQL, JavaScript, Flask, React, etc.)
- Experience requirement is 0–7 years (not Principal/Staff/Distinguished)
- Sponsorship signals present OR employer type is inherently cap-exempt (universities, government)
- No explicit dealbreaker language

### SKIP if:
- "No sponsorship" / "unable to sponsor" / "must be authorized to work"
- US/EU citizenship required
- Security clearance required
- Role requires skills not in candidate's profile
- 10+ years experience required

---

## Notes

- **Collect as many leads as possible** — this is a discovery workflow, quantity matters
- **Do NOT apply to jobs** — output links only
- **Do NOT generate resumes or cover letters**
- Search multiple pages per job board (at least 3–5 pages)
- Prefer direct employer posting links over aggregator search result pages
- The `data/seen-leads.json` file tracks URLs already collected to avoid duplicates
- Old application materials (resumes, cover letters, screenshots) are archived in `output/archived/`
