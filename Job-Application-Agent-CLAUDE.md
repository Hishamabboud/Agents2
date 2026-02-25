# Job Application Agent — CLAUDE.md
You are building an autonomous job application agent that runs using Claude Code on a Max subscription. Follow these instructions step by step.

## Project Goal
Build a fully autonomous system that:
1. Searches job boards for matching roles at cap-exempt employers
2. Checks for sponsorship dealbreakers and scores jobs against my profile
3. Tailors my resume and generates cover letters per job
4. Fills out and submits applications via browser automation
5. Logs everything to a tracker

## Step 1: Project Setup
```
mkdir -p ~/job-hunter/.claude/agents
cd ~/job-hunter
git init
npm init -y
npm install playwright @anthropic-ai/mcp-playwright
npx playwright install chromium
pip install beautifulsoup4 requests --break-system-packages
```

Create this folder structure:
```
~/job-hunter/
├── CLAUDE.md              (this file)
├── .claude/
│   ├── settings.json      (MCP config)
│   └── agents/
│       └── job-applier.md (custom agent definition)
├── profile/
│   ├── resume.md          (my full resume in markdown)
│   ├── resume.pdf         (my current PDF resume)
│   ├── preferences.md     (job search preferences)
│   └── cover-letter-template.md
├── output/
│   ├── tailored-resumes/  (generated per job)
│   ├── cover-letters/     (generated per job)
│   └── screenshots/       (proof of submission)
├── data/
│   └── applications.json  (application tracker)
├── scripts/
│   ├── search.py          (job board scraper)
│   ├── score.py           (job matching scorer)
│   ├── tailor.py          (resume tailor)
│   ├── apply.py           (browser automation apply)
│   └── run.sh             (orchestrator script)
└── logs/
    └── agent.log
```

## Step 2: MCP Configuration
Create `.claude/settings.json`:
```json
{
  "mcpServers": {
    "playwright": {
      "command": "npx",
      "args": ["@anthropic-ai/mcp-playwright"]
    }
  },
  "permissions": {
    "allow": [
      "Bash(npm:*)",
      "Bash(node:*)",
      "Bash(python3:*)",
      "Bash(npx:*)",
      "mcp__playwright__*",
      "Read(*)",
      "Write(~/job-hunter/*)"
    ]
  }
}
```

## Step 3: Custom Agent Definition
Create `.claude/agents/job-applier.md`:
```markdown
---
name: Job Applier
description: Autonomous agent that searches cap-exempt jobs, tailors resumes, and applies. Use for all job hunting tasks.
model: sonnet
tools:
  - Bash
  - Read
  - Write
  - WebFetch
  - mcp__playwright__browser_navigate
  - mcp__playwright__browser_click
  - mcp__playwright__browser_type
  - mcp__playwright__browser_screenshot
  - mcp__playwright__browser_snapshot
---

You are an autonomous job application agent focused on finding H-1B sponsorship opportunities at cap-exempt employers. You work in ~/job-hunter/.

## Your Workflow

### Phase 1: Discover
- Read profile/preferences.md for search criteria
- Scrape job boards using scripts/search.py or direct web fetching
- Target: HigherEdJobs, Indeed, LinkedIn, Glassdoor, USAJobs, Chronicle Vitae
- PRIORITY: University jobs, government agencies, nonprofit research organizations
- Save raw listings to data/raw-jobs.json

### Phase 2: Dealbreaker Check & Score
- Read profile/resume.md
- For each job, FIRST check for INSTANT SKIP conditions:
  - "No sponsorship" / "Unable to sponsor"
  - "Must be US citizen or green card holder"
  - "Authorization to work without sponsorship"
  - Credit unions (NOT cap-exempt)
  - K-12 school districts (NOT cap-exempt)
  - For-profit companies (NOT cap-exempt unless exceptional)
- For remaining jobs, score relevance 1-10 based on:
  - Cap-exempt status (+3 points automatic boost)
  - Skills match (Python, C#, SQL, JavaScript, Flask, ASP.NET)
  - Experience level match (5 years experience)
  - Tech stack overlap
  - Salary range (minimum $70k)
- Filter: only proceed with jobs scoring 6+
- Save scored jobs to data/scored-jobs.json

### Phase 3: Tailor
- For each qualifying job:
  - Generate a tailored resume emphasizing relevant experience
  - Mirror exact keywords from job description for ATS
  - Reorder skills section to match their requirements
  - Keep resume to ONE PAGE, ~400 words max
  - Save as output/tailored-resumes/{company}-{role}.md
  - Generate a personalized cover letter (500-600 words)
  - Use simple, human language - no corporate jargon
  - Connect to company mission authentically
  - Save as output/cover-letters/{company}-{role}.md
  - Convert to PDF if needed

### Phase 4: Apply
- Use Playwright MCP to:
  - Navigate to the application page
  - Fill in personal details
  - Upload tailored resume
  - Paste/type cover letter
  - Answer screening questions intelligently
  - Screenshot before submitting
  - Submit the application
- Save screenshot to output/screenshots/

### Phase 5: Log
- Update data/applications.json with:
  - Company name, role title, URL
  - Cap-exempt status (yes/no)
  - Salary (if listed)
  - Date applied
  - Tailored resume used
  - Cover letter used
  - Status: "applied" / "failed" / "skipped"
  - Notes on any issues

## Rules
- NEVER fabricate experience, skills, or qualifications
- NEVER apply to the same job twice (check applications.json)
- ALWAYS screenshot before submitting
- ALWAYS save tailored materials before applying
- ALWAYS check for sponsorship dealbreakers FIRST
- Skip jobs requiring skills not in my resume
- Prioritize cap-exempt employers (universities, government, nonprofit research)
- If a form is too complex or requires video/assessment, mark as "skipped" with reason
- If CAPTCHA blocks you, mark as "failed" and move on
- Respect rate limits: wait 30-60 seconds between applications on the same site
- NEVER mention H-1B or visa status in cover letters or applications
```

## Step 4: Profile Files

Create `profile/preferences.md`:
```markdown
# Job Search Preferences

## URGENT TIMELINE
- Current status: STEM OPT ending May 2026
- Need H-1B sponsorship by mid-May 2026
- MUST prioritize cap-exempt employers

## Target Roles
- Full Stack Developer
- Software Engineer
- Backend Developer
- Data Engineer
- Application Developer
- Software Developer
- Python Developer
- .NET Developer
- Database Developer

## Cap-Exempt Employers (PRIORITY)
- Universities (public, private, community colleges)
- University-affiliated hospitals
- Government agencies (federal, state, local, tribal)
- Nonprofit research organizations (501c3)
- Government research labs

## Required
- Location: Remote USA or willing to relocate anywhere in US
- Language: English
- Minimum salary: $70,000/year (skip if not listed or below this)
- NO explicit "no sponsorship" language

## Tech Stack (My Skills)
- Backend: Python/Flask, C#/ASP.NET, PHP
- Frontend: JavaScript, Vue.js, React, Angular, HTML, CSS
- Databases: SQL Server, MySQL, PostgreSQL, T-SQL, Stored Procedures
- Tools: Git, Docker, REST APIs, CI/CD, Agile/Scrum
- Data: ETL pipelines, data modeling, database design

## Preferred
- Industries: Healthcare, Education, Research, Government, Nonprofit
- Company mission: Public good, social impact, education, healthcare
- Tech stack matches: Python, C#, SQL, JavaScript frameworks

## INSTANT SKIP (Dealbreakers)
- "No sponsorship" or "unable to sponsor work visas"
- "Must be authorized to work without sponsorship"
- "US citizen or permanent resident required"
- Credit unions (NOT cap-exempt)
- K-12 school districts (NOT cap-exempt)
- Federal contractors requiring security clearance/citizenship
- For-profit companies (unless exceptional fit)
- Roles requiring 10+ years experience
- Principal/Staff/Distinguished engineer levels

## Job Boards to Search
1. HigherEdJobs.com (university jobs)
2. Chronicle Vitae (academic jobs)
3. USAJobs.gov (federal government)
4. Indeed (filter: nonprofit, university, government)
5. LinkedIn (filter: nonprofit, education, government)
6. Glassdoor (filter: nonprofit organizations)
7. Idealist.org (nonprofit jobs)

## My Details for Forms
- Full Name: Mohamad Abboud
- Email: mohammad.a.abboud@gmail.com
- Phone: (406) 920-5162
- LinkedIn: [ADD YOUR LINKEDIN]
- GitHub: MoAbboud
- Current Location: St. Paul, Minnesota
- Willing to Relocate: Yes, anywhere in US
- Work Authorization: F-1 STEM OPT (valid through May 2026)
```

Create `profile/resume.md` - paste your latest resume here:
```markdown
Mohamad Abboud
mohammad.a.abboud@gmail.com | (406) 920-5162 | St. Paul, Minnesota | GitHub: MoAbboud

TECHNICAL SKILLS
Programming Languages: Python, C#, JavaScript, SQL, PHP, HTML, CSS
Frameworks & Libraries: Flask, ASP.NET, Vue.js, React, Angular, Bootstrap
Databases: PostgreSQL, SQL Server, MySQL, T-SQL, Stored Procedures, Query Optimization, Data Modeling
Development Tools: Git/GitHub, Docker, REST APIs, CI/CD, Agile/Scrum, ClickUp
Cloud & Hosting: SiteGround, Cloudways, SSH, FTP

EXPERIENCE

Full Stack Developer | Tekkii | January 2023 - January 2026 | Kansas City, KS
- Led backend development for Kansas City Drayage, KidsCloset, KC Sports Directory, and interactive display at The College Basketball Experience, enhancing features using PHP, SQL, and advanced CSS
- Built automated EDI capture and sending features, streamlining logistics data exchange and reducing manual processing time
- Developed and maintained RESTful APIs, integrating OneSignal for push notifications and programming mobile application features
- Transformed an e-commerce platform's backend and database layer, leading to the app's successful acquisition
- Integrated third-party services including PayPal for transactions, SendGrid for email automation, and cloud hosting platforms
- Managed server infrastructure using SSH and FTP, performed application migrations between servers, and maintained version control with Git
- Collaborated in Agile Scrum environment with weekly sprint reviews, using ClickUp to prioritize tasks and ensure timely project delivery
- Communicated complex technical concepts in plain language to clients and end users, ensuring clear understanding of project requirements and progress

Software Engineer | Allied Engineering Group | June 2019 - June 2021 | Beirut, Lebanon
- Designed and developed SWIFT transaction handling applications using C#/ASP.NET, integrating with SQL Server to process secure financial transactions for 400+ banking clients across 40+ countries
- Optimized SQL queries for data retrieval and display in Telerik grids, improving application performance and user experience across financial solutions
- Monitored and analyzed SQL and application logs to identify and resolve errors, ensuring uninterrupted operations for banking clients
- Built and maintained database schemas, stored procedures, and complex queries for high-volume transaction processing systems
- Customized user interfaces based on client requirements, adding new features and improving usability, resulting in higher client satisfaction
- Participated in Agile development with sprint planning, daily scrums, and retrospectives, identifying risks and blockers for the team

EDUCATION
University of Missouri-Kansas City - Master of Science in Computer Science | 2021 - 2023
- Relevant Coursework: Software Engineering, Advanced Database Systems, Data Structures and Algorithms, Enterprise Application Development
- Pneumonia Detection App: Developed machine learning model using Python to analyze chest X-ray images for pneumonia detection
```

Create `profile/cover-letter-template.md`:
```markdown
# Cover Letter Template

Use this structure. Keep it simple, human, and mission-focused. 500-600 words max.

Dear Hiring Manager,

[Opening: Why this specific role and company excites me. Connect to their mission authentically. 1-2 sentences.]

[Tekkii paragraph: Relevant experience from current role. Mirror their job description keywords. Show what I built and how it relates to what they need. Be specific about projects like Kansas City Drayage EDI system, KidsCloset e-commerce transformation, KC Sports Directory database, or College Basketball Experience interactive hardware integration.]

[Allied paragraph: Previous role experience. Highlight C#/ASP.NET and SQL Server work for 400+ banking clients across 40+ countries. Emphasize database design, stored procedures, and working with international teams.]

[Gap acknowledgment if needed: Be honest about missing skills while emphasizing transferable skills and ability to learn quickly. Reference master's degree and ability to pick up new technologies.]

[Healthcare/mission connection if relevant: Brother is physician, sister is psychologist. Built pneumonia detection ML app. Passionate about using technology for public good / education / healthcare / social impact.]

[Closing: Reiterate interest, mention relocation willingness, call to action. Keep it warm and human.]

Best regards,
Mohamad Abboud

## Key Projects to Reference
- Kansas City Drayage (KCD): Built EDI processing system from scratch for logistics data exchange
- KidsCloset.biz: E-commerce platform backend transformation leading to successful acquisition
- KC Election System: Government election application updates (mention for government roles)
- KC Sports Directory: Community sports database supported by Kansas City Healthy Lifestyles Collaborative and Kansas City Royals Foundation
- College Basketball Experience: Interactive display connecting hardware (cameras, TVs, teleprompter) to custom application
- Pneumonia Detection App: Machine learning model for medical diagnostics (mention for healthcare roles)

## Brother/Sister Healthcare Connection
- Brother: Physician
- Sister: Psychologist
- Use when applying to healthcare organizations or medical research positions
```

## Step 5: Scripts

### search.py - Job Board Scraper
Build a Python script that:
- Takes search keywords and location from preferences.md
- Scrapes job listings from configured job boards
- PRIORITIZES: HigherEdJobs, Chronicle Vitae, USAJobs, nonprofit job boards
- Uses requests + BeautifulSoup for static sites
- Falls back to Playwright for JS-heavy sites
- For each job, attempts to identify cap-exempt status from employer name/description
- Outputs structured JSON: `{title, company, location, url, description, date_posted, salary, cap_exempt_likely, sponsorship_flags}`
- Deduplicates by URL
- Saves to data/raw-jobs.json

### score.py - Job Matcher & Dealbreaker Detector
Build a Python script that:
- Loads raw-jobs.json and resume.md
- FIRST: Checks for dealbreakers in description:
  - "no sponsorship" / "unable to sponsor"
  - "must be US citizen" / "security clearance required"
  - "authorized to work without sponsorship"
  - Credit union or K-12 employer
  - Marks as SKIP if dealbreaker found
- THEN: Scores remaining jobs 1-10:
  - Cap-exempt status: +3 points
  - Skills match (keyword overlap with my tech stack): 0-4 points
  - Experience level match (5 years target): 0-2 points
  - Salary listed and above $70k: +1 point
- Filters out jobs already in applications.json
- Filters jobs scoring below 6
- Saves scored results to data/scored-jobs.json with reasoning

### tailor.py - Resume & Cover Letter Generator
Build a Python script that:
- For each high-scoring job, generates tailored resume
- Mirrors exact keywords from job description (ATS optimization)
- Reorders Technical Skills section to match their requirements first
- Adjusts bullet points to emphasize relevant experience
- Keeps resume to ONE PAGE (~400 words)
- Generates personalized cover letter (500-600 words)
- Uses simple, human language - connects to company mission
- References relevant projects (KCD, KidsCloset, KC Sports Directory, etc.)
- Mentions healthcare connection if relevant (brother physician, sister psychologist)
- NEVER mentions H-1B or visa status
- Saves both to output/ directories
- Uses Claude (via subprocess or API) for generation

### apply.py - Application Submitter
Build a Python script that:
- Uses Playwright to automate form filling
- Handles common ATS platforms (Workday, Greenhouse, Lever, Taleo, iCIMS)
- Uploads resume PDF
- Types or pastes cover letter content
- Fills standard fields (name, email, phone, location)
- Answers common screening questions:
  - "Are you authorized to work?" -> "Yes" (true for OPT status)
  - "Do you require sponsorship?" -> Skip or answer honestly based on form
  - Years of experience -> 5
  - Salary expectations -> Based on job posting or $85k
- Screenshots before submission
- Submits and logs result
- Handles failures gracefully

### run.sh - Orchestrator
```bash
#!/bin/bash
cd ~/job-hunter
echo "$(date): Starting job hunt cycle" >> logs/agent.log

python3 scripts/search.py >> logs/agent.log 2>&1
echo "$(date): Search complete" >> logs/agent.log

python3 scripts/score.py >> logs/agent.log 2>&1
echo "$(date): Scoring complete" >> logs/agent.log

python3 scripts/tailor.py >> logs/agent.log 2>&1
echo "$(date): Tailoring complete" >> logs/agent.log

python3 scripts/apply.py >> logs/agent.log 2>&1
echo "$(date): Applications submitted" >> logs/agent.log

echo "$(date): Cycle complete" >> logs/agent.log
```

## Step 6: Running Modes

### Interactive (watch it work)
```bash
cd ~/job-hunter
claude
# Then say: "Run the full job application pipeline. Search cap-exempt jobs, check dealbreakers, score, tailor, and apply to top 5."
```

### Headless one-shot
```bash
cd ~/job-hunter
claude -p "Run job hunt cycle: search for Software Engineer roles at universities and nonprofits, score them, tailor resume for top 5, and apply. Log everything."
```

### Background with subagent
From within Claude Code, press Ctrl+B to send a running task to background while you keep working.

### Scheduled (cron)
```bash
# Add to crontab: run every weekday at 9 AM
0 9 * * 1-5 cd ~/job-hunter && claude -p "Run daily job search and apply cycle. Focus on cap-exempt employers. Apply to top 5 new matches." >> ~/job-hunter/logs/agent.log 2>&1
```

### Continuous loop with tmux
```bash
tmux new -s jobhunter
cd ~/job-hunter
while true; do
  claude -p "Run one job hunt cycle. Search cap-exempt jobs, apply to top 3-5 matches."
  echo "Sleeping 6 hours..."
  sleep 21600
done
```

## Step 7: Application Tracker

`data/applications.json` structure:
```json
[
  {
    "id": "uuid",
    "company": "Company Name",
    "role": "Job Title",
    "url": "https://...",
    "cap_exempt": true,
    "salary": "$85,000 - $110,000",
    "date_applied": "2026-02-25",
    "score": 8.5,
    "status": "applied",
    "resume_file": "output/tailored-resumes/company-role.md",
    "cover_letter_file": "output/cover-letters/company-role.md",
    "screenshot": "output/screenshots/company-role.png",
    "notes": "",
    "response": "pending"
  }
]
```

## Important Notes
- This project uses Claude Max subscription via Claude Code - no API keys needed
- All browser automation goes through the Playwright MCP server
- Never store passwords in plain text - use environment variables or .env file
- For LinkedIn: log in manually first, save cookies, then reuse the session
- Test each phase independently before running the full pipeline
- Start with 2-3 applications to verify everything works before scaling up
- PRIORITY: Cap-exempt employers (universities, government, nonprofit research)
- CRITICAL: Always check for "no sponsorship" dealbreakers FIRST
- Timeline is urgent: May 2026 deadline for H-1B sponsorship
- Focus on quality over quantity - better to apply to 5 good cap-exempt jobs than 20 random ones
