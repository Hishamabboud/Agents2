# Job Search Agent Instructions for Claude Code

## Project Overview

Build an autonomous job search system for Mohamad Abboud that:
- Discovers job postings from multiple sources
- Evaluates fit against strict requirements (H-1B cap-exempt employers, software development roles)
- Generates ATS-optimized resumes and personalized cover letters
- Creates an interactive HTML tracker with click tracking
- Runs autonomously in the background

**Critical Context**: Mohamad needs H-1B sponsorship by May 2026 (STEM OPT expires). MUST target cap-exempt employers only (universities, government, nonprofit research, teaching hospitals). Cannot wait for H-1B lottery.

---

## Project Setup & Architecture

### 1. Initialize Project Structure

```
job-search-agent/
├── src/
│   ├── scraper.py          # Job URL discovery and content extraction
│   ├── evaluator.py        # Job fit assessment using Claude API
│   ├── resume_generator.py # ATS-optimized resume creation
│   ├── cover_letter_gen.py # Mission-specific cover letter generation
│   ├── tracker.py          # HTML tracker generation
│   └── utils.py            # Helper functions
├── data/
│   ├── jobs_found.json     # All discovered jobs
│   ├── jobs_evaluated.json # Evaluated jobs with scores
│   ├── master_resume.json  # Base resume content
│   └── master_cover.json   # Base cover letter template
├── output/
│   ├── tracker.html        # Main tracking interface
│   └── applications/       # Generated resumes & cover letters
├── logs/
│   ├── search_log.txt      # Search activity
│   └── errors.log          # Error tracking
├── config.py               # Configuration and search parameters
├── requirements.txt        # Python dependencies
└── main.py                 # Orchestrator/scheduler
```

### 2. Install Required Dependencies

Create `requirements.txt`:
```
anthropic>=0.18.0
beautifulsoup4>=4.12.0
requests>=2.31.0
selenium>=4.15.0
webdriver-manager>=4.0.0
python-docx>=1.1.0
schedule>=1.2.0
aiohttp>=3.9.0
jinja2>=3.1.0
python-dotenv>=1.0.0
lxml>=4.9.0
```

Install:
```bash
pip install -r requirements.txt --break-system-packages
```

---

## Core Components

### 3. Configuration File (config.py)

```python
import os
from dotenv import load_dotenv

load_dotenv()

# API Configuration
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
CLAUDE_MODEL = "claude-sonnet-4-20250514"

# Search Configuration
SEARCH_QUERIES = [
    "Software Developer university",
    "Software Engineer .edu",
    "Application Developer government",
    "Full Stack Developer nonprofit research",
    "Backend Developer teaching hospital",
    "Python Developer cap-exempt",
    "Software Developer state government",
    "Application Developer federal government",
    ".NET Developer university",
    "Full Stack Engineer teaching hospital"
]

# Job Board URLs
JOB_BOARDS = {
    "indeed": "https://www.indeed.com/jobs",
    "linkedin": "https://www.linkedin.com/jobs/search",
    "usajobs": "https://www.usajobs.gov/Search/Results",
    "higheredjobs": "https://www.higheredjobs.com/search",
    "glassdoor": "https://www.glassdoor.com/Job/jobs.htm"
}

# Cap-Exempt Indicators
CAP_EXEMPT_INDICATORS = [
    ".edu", ".gov", "university", "college", 
    "teaching hospital", "research institute",
    "national laboratory", "state agency",
    "federal agency", "state university",
    "community college", "public university"
]

CAP_EXEMPT_DOMAINS = [
    ".edu", ".gov", ".ac.uk", "nih.gov", "nasa.gov"
]

# Dealbreaker Phrases
DEALBREAKER_PHRASES = [
    "no sponsorship",
    "unable to sponsor",
    "must be authorized to work without sponsorship",
    "must be authorized to work for any employer",
    "us citizen required",
    "u.s. citizen required",
    "permanent resident required",
    "green card required",
    "security clearance required",
    "citizenship required"
]

# Tech Stack Priorities (for scoring)
TECH_STACK = {
    "high_priority": [
        "python", "flask", "c#", ".net", "asp.net", "php",
        "javascript", "vue.js", "vue", "react", "angular",
        "sql", "postgresql", "mysql", "sql server",
        "rest api", "restful"
    ],
    "medium_priority": [
        "docker", "git", "ci/cd", "agile", "scrum",
        "backend", "full stack", "database", "sql",
        "html", "css", "bootstrap"
    ],
    "low_priority": [
        "aws", "azure", "gcp", "kubernetes", "node.js"
    ]
}

# Experience Range
MIN_EXPERIENCE_YEARS = 3
MAX_EXPERIENCE_YEARS = 8
IDEAL_EXPERIENCE_YEARS = 5

# Fit Score Thresholds
EXCELLENT_THRESHOLD = 80
GOOD_THRESHOLD = 65
BORDERLINE_THRESHOLD = 50

# Rate Limiting
REQUEST_DELAY = 3  # seconds between requests
MAX_RETRIES = 3
RETRY_DELAY = 5

# Scheduling
SEARCH_INTERVAL_HOURS = 6
SEARCH_TIMES = ["09:00", "15:00", "21:00"]  # Daily search times

# File Paths
DATA_DIR = "data"
OUTPUT_DIR = "output"
APPLICATIONS_DIR = "output/applications"
LOGS_DIR = "logs"
```

---

### 4. Job Scraper (scraper.py)

```python
import time
import json
import hashlib
import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
import config
import logging

logger = logging.getLogger(__name__)

class JobScraper:
    def __init__(self):
        self.seen_jobs = self.load_seen_jobs()
        
    def load_seen_jobs(self):
        """Load previously seen job URLs to avoid duplicates"""
        try:
            with open(f"{config.DATA_DIR}/jobs_found.json", 'r') as f:
                jobs = json.load(f)
                return set(job['url'] for job in jobs)
        except FileNotFoundError:
            return set()
    
    def get_job_hash(self, url, title, company):
        """Create unique hash for job to detect duplicates"""
        content = f"{url}{title}{company}".lower()
        return hashlib.md5(content.encode()).hexdigest()
    
    def setup_driver(self):
        """Configure Selenium WebDriver for scraping"""
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
        
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        return driver
    
    async def search_job_boards(self):
        """Search multiple job boards for relevant positions"""
        all_jobs = []
        
        for query in config.SEARCH_QUERIES:
            logger.info(f"Searching for: {query}")
            
            # Search Indeed
            indeed_jobs = await self.search_indeed(query)
            all_jobs.extend(indeed_jobs)
            time.sleep(config.REQUEST_DELAY)
            
            # Search USAJobs (government positions)
            usajobs = await self.search_usajobs(query)
            all_jobs.extend(usajobs)
            time.sleep(config.REQUEST_DELAY)
            
            # Search HigherEdJobs (university positions)
            highered_jobs = await self.search_higheredjobs(query)
            all_jobs.extend(highered_jobs)
            time.sleep(config.REQUEST_DELAY)
        
        # Remove duplicates
        unique_jobs = self.deduplicate_jobs(all_jobs)
        logger.info(f"Found {len(unique_jobs)} unique jobs")
        
        return unique_jobs
    
    async def search_indeed(self, query):
        """Search Indeed for jobs"""
        jobs = []
        try:
            driver = self.setup_driver()
            url = f"{config.JOB_BOARDS['indeed']}?q={query.replace(' ', '+')}"
            driver.get(url)
            time.sleep(2)
            
            # Parse job cards
            soup = BeautifulSoup(driver.page_source, 'html.parser')
            job_cards = soup.find_all('div', class_='job_seen_beacon')
            
            for card in job_cards[:20]:  # Limit to 20 per query
                try:
                    title_elem = card.find('h2', class_='jobTitle')
                    company_elem = card.find('span', class_='companyName')
                    location_elem = card.find('div', class_='companyLocation')
                    
                    if title_elem and company_elem:
                        job_url = "https://www.indeed.com" + title_elem.find('a')['href']
                        
                        if job_url not in self.seen_jobs:
                            jobs.append({
                                'url': job_url,
                                'title': title_elem.get_text(strip=True),
                                'company': company_elem.get_text(strip=True),
                                'location': location_elem.get_text(strip=True) if location_elem else '',
                                'source': 'Indeed',
                                'search_query': query
                            })
                except Exception as e:
                    logger.error(f"Error parsing Indeed job card: {e}")
                    continue
            
            driver.quit()
        except Exception as e:
            logger.error(f"Error searching Indeed: {e}")
        
        return jobs
    
    async def search_usajobs(self, query):
        """Search USAJobs.gov for government positions"""
        jobs = []
        try:
            # USAJobs has an API - use it for better results
            api_url = "https://data.usajobs.gov/api/search"
            headers = {
                'Host': 'data.usajobs.gov',
                'User-Agent': config.USER_AGENT,
                'Authorization-Key': config.USAJOBS_API_KEY  # Get free key from usajobs.gov
            }
            params = {
                'Keyword': query,
                'ResultsPerPage': 20
            }
            
            response = requests.get(api_url, headers=headers, params=params)
            if response.status_code == 200:
                data = response.json()
                for item in data.get('SearchResult', {}).get('SearchResultItems', []):
                    job = item['MatchedObjectDescriptor']
                    job_url = job['ApplyURI'][0] if job.get('ApplyURI') else ''
                    
                    if job_url and job_url not in self.seen_jobs:
                        jobs.append({
                            'url': job_url,
                            'title': job['PositionTitle'],
                            'company': job['OrganizationName'],
                            'location': job['PositionLocationDisplay'],
                            'source': 'USAJobs',
                            'search_query': query
                        })
        except Exception as e:
            logger.error(f"Error searching USAJobs: {e}")
        
        return jobs
    
    async def search_higheredjobs(self, query):
        """Search HigherEdJobs for university positions"""
        jobs = []
        try:
            driver = self.setup_driver()
            url = f"{config.JOB_BOARDS['higheredjobs']}?keyword={query.replace(' ', '+')}"
            driver.get(url)
            time.sleep(2)
            
            soup = BeautifulSoup(driver.page_source, 'html.parser')
            job_listings = soup.find_all('div', class_='job-listing')
            
            for listing in job_listings[:20]:
                try:
                    title_elem = listing.find('a', class_='job-title-link')
                    company_elem = listing.find('div', class_='institution')
                    location_elem = listing.find('div', class_='location')
                    
                    if title_elem and company_elem:
                        job_url = title_elem['href']
                        if not job_url.startswith('http'):
                            job_url = f"https://www.higheredjobs.com{job_url}"
                        
                        if job_url not in self.seen_jobs:
                            jobs.append({
                                'url': job_url,
                                'title': title_elem.get_text(strip=True),
                                'company': company_elem.get_text(strip=True),
                                'location': location_elem.get_text(strip=True) if location_elem else '',
                                'source': 'HigherEdJobs',
                                'search_query': query
                            })
                except Exception as e:
                    logger.error(f"Error parsing HigherEdJobs listing: {e}")
                    continue
            
            driver.quit()
        except Exception as e:
            logger.error(f"Error searching HigherEdJobs: {e}")
        
        return jobs
    
    def deduplicate_jobs(self, jobs):
        """Remove duplicate jobs based on URL and hash"""
        unique = {}
        for job in jobs:
            job_hash = self.get_job_hash(job['url'], job['title'], job['company'])
            if job_hash not in unique:
                unique[job_hash] = job
        return list(unique.values())
    
    async def extract_job_content(self, job):
        """Extract full job description and requirements"""
        try:
            driver = self.setup_driver()
            driver.get(job['url'])
            time.sleep(2)
            
            soup = BeautifulSoup(driver.page_source, 'html.parser')
            
            # Extract job description (varies by site)
            description = ""
            
            # Common description containers
            desc_selectors = [
                {'class': 'jobsearch-jobDescriptionText'},  # Indeed
                {'id': 'job-description'},
                {'class': 'job-description'},
                {'class': 'description'},
                {'id': 'jobDescriptionText'}
            ]
            
            for selector in desc_selectors:
                elem = soup.find('div', selector)
                if elem:
                    description = elem.get_text(separator='\n', strip=True)
                    break
            
            if not description:
                # Fallback: get all text from page
                description = soup.get_text(separator='\n', strip=True)
            
            job['description'] = description
            job['description_length'] = len(description)
            
            driver.quit()
            
            return job
            
        except Exception as e:
            logger.error(f"Error extracting job content from {job['url']}: {e}")
            return None
    
    async def verify_cap_exempt_employer(self, company_name):
        """Verify if employer is cap-exempt for H-1B"""
        try:
            # Check domain indicators
            company_lower = company_name.lower()
            for indicator in config.CAP_EXEMPT_INDICATORS:
                if indicator in company_lower:
                    return {
                        'is_cap_exempt': True,
                        'confidence': 'high',
                        'evidence': f'Company name contains "{indicator}"'
                    }
            
            # Google search for verification
            query = f"{company_name} H-1B cap exempt"
            search_url = f"https://www.google.com/search?q={query.replace(' ', '+')}"
            
            headers = {'User-Agent': 'Mozilla/5.0'}
            response = requests.get(search_url, headers=headers)
            
            if response.status_code == 200:
                text = response.text.lower()
                
                # Look for positive indicators
                positive_signals = [
                    'cap-exempt', 'cap exempt', 'university', 
                    'teaching hospital', 'government', 'nonprofit research'
                ]
                
                # Look for negative indicators
                negative_signals = [
                    'not cap-exempt', 'cap-subject', 'for-profit'
                ]
                
                positive_count = sum(1 for signal in positive_signals if signal in text)
                negative_count = sum(1 for signal in negative_signals if signal in text)
                
                if positive_count > negative_count:
                    return {
                        'is_cap_exempt': True,
                        'confidence': 'medium',
                        'evidence': f'Search found {positive_count} positive indicators'
                    }
                elif negative_count > 0:
                    return {
                        'is_cap_exempt': False,
                        'confidence': 'medium',
                        'evidence': f'Search found {negative_count} negative indicators'
                    }
            
            # Default: unknown
            return {
                'is_cap_exempt': None,
                'confidence': 'unknown',
                'evidence': 'Could not verify cap-exempt status'
            }
            
        except Exception as e:
            logger.error(f"Error verifying cap-exempt status for {company_name}: {e}")
            return {
                'is_cap_exempt': None,
                'confidence': 'error',
                'evidence': str(e)
            }
```

---

### 5. Job Evaluator (evaluator.py)

```python
import json
import asyncio
from anthropic import Anthropic
import config
import logging

logger = logging.getLogger(__name__)

class JobEvaluator:
    def __init__(self):
        self.client = Anthropic(api_key=config.ANTHROPIC_API_KEY)
        self.master_resume = self.load_master_resume()
        self.evaluation_criteria = self.load_evaluation_criteria()
    
    def load_master_resume(self):
        """Load Mohamad's resume content"""
        resume_text = """
Mohamad Abboud
mohammad.a.abboud@gmail.com | (406) 920-5162 | St. Paul, Minnesota

TECHNICAL SKILLS
Backend Development: Python/Flask, RESTful APIs, Data Pipelines, System Integration, Object-Oriented Programming
Languages & Frameworks: Python/Flask, C#/ASP.NET, JavaScript (Vue.js, React, Angular), SQL
Databases: PostgreSQL, SQL Server, MySQL, Database Design, Stored Procedures, Query Optimization, Data Modeling
DevOps & Tools: Git/GitHub, CI/CD Pipelines, Docker, Automated Testing, Code Review, Technical Documentation
Development Practices: SDLC, Agile/Scrum, Test-Driven Development, Software Architecture, Mentoring

EXPERIENCE
Full Stack Developer | Tekkii | January 2023 - January 2026 | Kansas City, KS
- Design and develop backend services and APIs using Python/Flask, building scalable web applications following software engineering best practices and design patterns
- Build complex data ingest pipelines and ETL workflows integrating multiple data sources, implementing data transformations and validation throughout the pipeline
- Design and optimize relational databases using PostgreSQL, SQL Server, and MySQL; write efficient queries, stored procedures, and implement robust data structures
- Implement comprehensive CI/CD pipelines using Git for version control and automated testing; actively participate in code reviews ensuring code quality and knowledge sharing
- Write maintainable, well-tested code following industry standards; break down features into manageable tasks and deliver implementations with minimal guidance
- Led development of enterprise EDI platform requiring complex data pipeline architecture, multi-system integration, and automated workflows, contributing to over 50% profit growth
- Mentor junior developers through code reviews, pair programming, and technical guidance; document architectural decisions and technical approaches for team knowledge sharing
- Collaborate with cross-functional teams in agile workflows including sprint planning, technical design discussions, retrospectives, and feature estimation

Software Engineer | Allied Engineering Group | June 2019 - June 2021 | Beirut, Lebanon
- Designed and developed backend systems and APIs using C#/ASP.NET with object-oriented programming principles for 400+ financial institutions across 40+ countries
- Built scalable data processing pipelines for SWIFT transaction platforms handling thousands of transactions daily with high availability and performance requirements
- Created database solutions using SQL Server including stored procedures, views, and optimized queries for mission-critical systems
- Participated in code reviews, technical design discussions, and provided guidance to junior team members on best practices and software architecture
- Implemented automated testing strategies and maintained comprehensive technical documentation for system features and architectural decisions

EDUCATION
University of Missouri-Kansas City - Master of Science in Computer Science | 2021 - 2023
Relevant Coursework: Software Engineering Principles, Advanced Database Systems, Data Structures and Algorithms, Distributed Systems
"""
        return resume_text
    
    def load_evaluation_criteria(self):
        """Load job evaluation criteria"""
        criteria = """
CRITICAL DEALBREAKERS (auto-reject):
1. Not cap-exempt employer (universities, government, nonprofit research, teaching hospitals with university affiliation)
2. Contains "no sponsorship" language
3. Not software development role (no BI, IT support, business analyst, process improvement)
4. 10+ years experience required
5. Required certification candidate doesn't have

EVALUATION CRITERIA:

Cap-Exempt Status (REQUIRED):
- Universities and colleges (public, private, community)
- Government agencies (federal, state, local)
- Nonprofit research organizations (primary mission = research)
- Teaching hospitals WITH formal university affiliation
- Government research labs

Role Type (MUST be software development):
- Building applications/features ✅
- Writing code (backend/frontend) ✅
- API development ✅
- Database programming ✅
NOT: Configuring vendor software, IT support, creating dashboards, process improvement

Experience Match:
- 3-6 years: GOOD FIT (candidate has 5 years)
- 7-8 years: BORDERLINE
- 10+ years: SKIP (too senior)
- Entry-level: OVERQUALIFIED

Tech Stack Fit:
Strong matches (prioritize):
- Python/Flask, C#/.NET/ASP.NET, PHP
- JavaScript frameworks (Vue, React, Angular)
- SQL Server, MySQL, PostgreSQL
- REST APIs, Full-stack development

Acceptable gaps (can learn):
- Specific frameworks not used
- Cloud platforms (willing to learn)
- Different databases (transferable)

FIT ASSESSMENT SCALE:
80-100% = EXCELLENT - Strong cap-exempt, software dev role, 3-6 years, 70%+ tech match, no major gaps
65-79% = GOOD - Cap-exempt, software dev, some tech gaps but transferable, slight experience mismatch
50-64% = BORDERLINE - Cap-exempt, development-adjacent, significant gaps, acknowledge honestly
Below 50% = SKIP
"""
        return criteria
    
    async def evaluate_job_with_claude(self, job_data):
        """Evaluate single job using Claude API"""
        prompt = f"""You are evaluating job fit for Mohamad Abboud who URGENTLY needs H-1B sponsorship by May 2026.

{self.evaluation_criteria}

JOB POSTING:
Title: {job_data['title']}
Company: {job_data['company']}
Location: {job_data['location']}
Description:
{job_data['description']}

CANDIDATE RESUME:
{self.master_resume}

CAP-EXEMPT VERIFICATION:
{json.dumps(job_data.get('cap_exempt', {}), indent=2)}

Respond in JSON format:
{{
    "fit_score": 0-100,
    "category": "EXCELLENT|GOOD|BORDERLINE|SKIP",
    "cap_exempt_verified": true/false,
    "is_software_dev": true/false,
    "dealbreakers": [],
    "tech_stack_match": 0-100,
    "experience_match": "description",
    "strengths": ["strength1", "strength2"],
    "gaps": ["gap1", "gap2"],
    "recommendation": "APPLY|SKIP",
    "reasoning": "detailed explanation"
}}"""
        
        try:
            message = self.client.messages.create(
                model=config.CLAUDE_MODEL,
                max_tokens=1000,
                messages=[{"role": "user", "content": prompt}]
            )
            
            response_text = message.content[0].text
            
            # Parse JSON from response
            # Remove markdown code blocks if present
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0]
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0]
            
            evaluation = json.loads(response_text.strip())
            
            # Add job metadata to evaluation
            evaluation['job_url'] = job_data['url']
            evaluation['job_title'] = job_data['title']
            evaluation['company'] = job_data['company']
            evaluation['location'] = job_data['location']
            evaluation['source'] = job_data['source']
            
            logger.info(f"Evaluated {job_data['title']} at {job_data['company']}: {evaluation['fit_score']}% - {evaluation['recommendation']}")
            
            return evaluation
            
        except Exception as e:
            logger.error(f"Error evaluating job {job_data['title']}: {e}")
            return None
    
    async def batch_evaluate_jobs(self, jobs):
        """Evaluate multiple jobs with rate limiting"""
        evaluations = []
        
        for i, job in enumerate(jobs):
            logger.info(f"Evaluating job {i+1}/{len(jobs)}: {job['title']}")
            
            evaluation = await self.evaluate_job_with_claude(job)
            if evaluation:
                evaluations.append(evaluation)
            
            # Rate limiting
            if i < len(jobs) - 1:
                await asyncio.sleep(2)  # 2 seconds between API calls
        
        # Save evaluations
        self.save_evaluations(evaluations)
        
        return evaluations
    
    def save_evaluations(self, evaluations):
        """Save evaluations to JSON file"""
        try:
            # Load existing evaluations
            try:
                with open(f"{config.DATA_DIR}/jobs_evaluated.json", 'r') as f:
                    existing = json.load(f)
            except FileNotFoundError:
                existing = []
            
            # Append new evaluations
            existing.extend(evaluations)
            
            # Save
            with open(f"{config.DATA_DIR}/jobs_evaluated.json", 'w') as f:
                json.dump(existing, f, indent=2)
            
            logger.info(f"Saved {len(evaluations)} evaluations")
            
        except Exception as e:
            logger.error(f"Error saving evaluations: {e}")
```

---

### 6. Resume Generator (resume_generator.py)

```python
import json
from anthropic import Anthropic
from docx import Document
from docx.shared import Pt, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH
import config
import logging

logger = logging.getLogger(__name__)

class ResumeGenerator:
    def __init__(self):
        self.client = Anthropic(api_key=config.ANTHROPIC_API_KEY)
    
    async def generate_ats_resume(self, job_evaluation, master_resume):
        """Generate ATS-optimized resume for specific job"""
        prompt = f"""Create an ATS-optimized one-page resume for this job posting.

RULES:
- Mirror job posting keywords (especially in skills section)
- Reorder skills to match their requirements first
- Keep all content truthful (only use real experience from master resume)
- Maintain one-page format (strict)
- Quantify achievements where possible
- Use action verbs from job posting
- DO NOT add experience candidate doesn't have
- DO NOT exaggerate or lie

JOB POSTING:
Title: {job_evaluation['job_title']}
Company: {job_evaluation['company']}
Key Requirements: {job_evaluation.get('tech_stack_requirements', 'See description')}

MASTER RESUME:
{master_resume}

Return resume in markdown format with these sections:
- Header (Name, Contact)
- Technical Skills (reordered to match job)
- Experience (bullet points tailored to emphasize relevant work)
- Education

Focus on making it ATS-friendly while highlighting fit for this specific role."""

        try:
            message = self.client.messages.create(
                model=config.CLAUDE_MODEL,
                max_tokens=2000,
                messages=[{"role": "user", "content": prompt}]
            )
            
            resume_markdown = message.content[0].text
            
            # Remove markdown code blocks if present
            if "```markdown" in resume_markdown:
                resume_markdown = resume_markdown.split("```markdown")[1].split("```")[0]
            elif "```" in resume_markdown:
                resume_markdown = resume_markdown.split("```")[1].split("```")[0]
            
            return resume_markdown.strip()
            
        except Exception as e:
            logger.error(f"Error generating resume: {e}")
            return None
    
    def convert_to_docx(self, markdown_resume, company_name):
        """Convert markdown resume to professional .docx"""
        try:
            doc = Document()
            
            # Set margins
            sections = doc.sections
            for section in sections:
                section.top_margin = Inches(0.5)
                section.bottom_margin = Inches(0.5)
                section.left_margin = Inches(0.75)
                section.right_margin = Inches(0.75)
            
            # Parse markdown and add to document
            lines = markdown_resume.split('\n')
            
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                
                # Header (name)
                if line.startswith('# '):
                    p = doc.add_paragraph(line[2:])
                    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                    run = p.runs[0]
                    run.font.size = Pt(16)
                    run.bold = True
                
                # Contact info
                elif '|' in line and '@' in line:
                    p = doc.add_paragraph(line)
                    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                    run = p.runs[0]
                    run.font.size = Pt(10)
                
                # Section headers
                elif line.startswith('## '):
                    p = doc.add_paragraph(line[3:])
                    run = p.runs[0]
                    run.font.size = Pt(12)
                    run.bold = True
                
                # Bullet points
                elif line.startswith('- ') or line.startswith('* '):
                    doc.add_paragraph(line[2:], style='List Bullet')
                
                # Regular paragraphs
                else:
                    doc.add_paragraph(line)
            
            # Save
            filename = f"{config.APPLICATIONS_DIR}/{company_name.replace(' ', '_')}_resume.docx"
            doc.save(filename)
            logger.info(f"Saved resume: {filename}")
            
            return filename
            
        except Exception as e:
            logger.error(f"Error converting to docx: {e}")
            return None
```

---

### 7. Cover Letter Generator (cover_letter_gen.py)

```python
import json
import requests
from anthropic import Anthropic
import config
import logging

logger = logging.getLogger(__name__)

class CoverLetterGenerator:
    def __init__(self):
        self.client = Anthropic(api_key=config.ANTHROPIC_API_KEY)
        self.master_cover_template = self.load_master_cover()
    
    def load_master_cover(self):
        """Load sample cover letter for style reference"""
        template = """
Dear Hiring Manager,

I am applying for the [POSITION] position at [ORGANIZATION] because I am excited about [MISSION/WORK]. With five years of experience developing backend services using Python/Flask, building complex data pipelines, and collaborating within cross-functional teams, I am eager to contribute my technical expertise to [ORGANIZATION]'s mission of [MISSION]. The opportunity to work on meaningful [TYPE OF WORK] while [IMPACT] is exactly the kind of impactful work I want to do.

At Tekkii, I design and develop backend services and APIs using Python/Flask, building scalable web applications that power enterprise systems. I create complex data ingest pipelines and ETL workflows that integrate multiple data sources, implementing validation and transformation logic throughout the pipeline. I break down features into manageable tasks, write maintainable and well-tested code, and deliver implementations following software engineering best practices. I led development of an enterprise EDI platform that required designing data pipeline architecture, building multi-system integrations, and implementing automated workflows. This project taught me how to architect robust backend systems, collaborate effectively with stakeholders to understand requirements, and deliver quality features that meet user needs.

I actively participate in code reviews, providing constructive feedback that helps maintain code quality and shares knowledge across the team. I mentor junior developers through pair programming and technical guidance, document architectural decisions for team knowledge sharing, and contribute to technical design discussions. I implement comprehensive CI/CD pipelines, write automated tests to ensure code reliability, and maintain technical documentation that helps new team members onboard effectively. At Allied Engineering Group, I built backend systems for 400+ financial institutions, participated in code reviews and design discussions, and provided guidance to junior engineers on software architecture and best practices.

I want to be transparent that while I have strong [RELEVANT SKILLS], my familiarity with [DOMAIN SPECIFIC KNOWLEDGE] is limited. However, my foundation in [TRANSFERABLE SKILLS] positions me to quickly learn [WHAT NEEDS TO BE LEARNED]. I am eager to gain an understanding of [DOMAIN] while contributing immediately through my [STRONG SKILLS].

I am drawn to [ORGANIZATION] because of its mission to [MISSION]. The opportunity to [SPECIFIC WORK], helping [BENEFICIARIES], aligns perfectly with my desire to use technology for [PURPOSE]. I am excited about joining [TEAM DESCRIPTION] where I can have a significant impact, help inform technical strategy, and grow my skills in a mission-driven environment. [RELOCATION/WORK ARRANGEMENT STATEMENT IF APPLICABLE].

Thank you for considering my application. I would welcome the opportunity to discuss how my [KEY SKILLS] can contribute to [ORGANIZATION]'s [TEAM/MISSION].

Sincerely,
Mohamad Abboud
"""
        return template
    
    async def research_company_mission(self, company_name):
        """Quick web search for company mission/values"""
        try:
            query = f"{company_name} mission statement values"
            search_url = f"https://www.google.com/search?q={query.replace(' ', '+')}"
            
            headers = {'User-Agent': 'Mozilla/5.0'}
            response = requests.get(search_url, headers=headers)
            
            if response.status_code == 200:
                # Very basic extraction - in production, use proper web scraping
                text = response.text
                # Look for mission-related keywords
                mission_keywords = ['mission', 'vision', 'values', 'purpose', 'dedicated to']
                
                # Extract snippets containing mission keywords
                snippets = []
                for keyword in mission_keywords:
                    if keyword in text.lower():
                        # Get surrounding text (very basic)
                        idx = text.lower().find(keyword)
                        snippet = text[max(0, idx-100):min(len(text), idx+200)]
                        snippets.append(snippet)
                
                return ' '.join(snippets[:2])  # Return first 2 snippets
            
            return "No mission information found"
            
        except Exception as e:
            logger.error(f"Error researching company mission: {e}")
            return "Research failed"
    
    async def generate_cover_letter(self, job_evaluation):
        """Generate personalized cover letter"""
        # Research company mission
        mission_info = await self.research_company_mission(job_evaluation['company'])
        
        prompt = f"""Write a 500-600 word cover letter for this job using Mohamad's voice and style.

REQUIREMENTS:
- Sound conversational and human (not corporate jargon)
- Tell a story connecting experience to their mission
- Be honest about gaps but frame positively
- Show genuine interest in organization's mission
- NEVER mention H-1B or visa (implied by situation)
- Demonstrate adaptability and eagerness to learn
- Use the template style as reference but customize for this job
- Keep it to ONE PAGE (500-600 words max)

TEMPLATE STYLE REFERENCE:
{self.master_cover_template}

JOB DETAILS:
Title: {job_evaluation['job_title']}
Company: {job_evaluation['company']}
Location: {job_evaluation['location']}

COMPANY MISSION/INFO:
{mission_info}

JOB STRENGTHS (from evaluation):
{json.dumps(job_evaluation.get('strengths', []), indent=2)}

JOB GAPS (from evaluation):
{json.dumps(job_evaluation.get('gaps', []), indent=2)}

Write a cover letter that:
1. Opens with excitement about the specific role and organization
2. Connects Mohamad's backend/pipeline experience to their needs
3. Acknowledges gaps honestly while emphasizing transferable skills
4. Shows genuine interest in their mission
5. Closes with enthusiasm about contributing

Return plain text cover letter (no formatting codes)."""

        try:
            message = self.client.messages.create(
                model=config.CLAUDE_MODEL,
                max_tokens=2000,
                messages=[{"role": "user", "content": prompt}]
            )
            
            cover_letter = message.content[0].text.strip()
            
            # Save to file
            filename = f"{config.APPLICATIONS_DIR}/{job_evaluation['company'].replace(' ', '_')}_cover_letter.txt"
            with open(filename, 'w') as f:
                f.write(cover_letter)
            
            logger.info(f"Generated cover letter: {filename}")
            
            return cover_letter
            
        except Exception as e:
            logger.error(f"Error generating cover letter: {e}")
            return None
```

---

### 8. HTML Tracker Generator (tracker.py)

```python
import json
from datetime import datetime
import config
import logging

logger = logging.getLogger(__name__)

class TrackerGenerator:
    def generate_tracker_html(self, evaluated_jobs):
        """Generate interactive HTML tracker"""
        
        # Sort jobs by fit score
        jobs = sorted(evaluated_jobs, key=lambda x: x['fit_score'], reverse=True)
        
        # Count by category
        excellent = len([j for j in jobs if j['fit_score'] >= config.EXCELLENT_THRESHOLD])
        good = len([j for j in jobs if config.GOOD_THRESHOLD <= j['fit_score'] < config.EXCELLENT_THRESHOLD])
        borderline = len([j for j in jobs if config.BORDERLINE_THRESHOLD <= j['fit_score'] < config.GOOD_THRESHOLD])
        
        # Generate job cards HTML
        job_cards_html = ""
        for i, job in enumerate(jobs):
            if job['recommendation'] != 'APPLY':
                continue
                
            category = self.get_category_class(job['fit_score'])
            cap_exempt_badge = self.get_cap_exempt_badge(job)
            
            strengths_html = "".join([f"<li>{s}</li>" for s in job.get('strengths', [])])
            gaps_html = "".join([f"<li>{g}</li>" for g in job.get('gaps', [])])
            
            company_safe = job['company'].replace(' ', '_').replace('/', '_')
            
            job_cards_html += f"""
            <div class="job-card {category}" data-category="{category}">
                <div class="job-header">
                    <h2>{job['job_title']}</h2>
                    <span class="fit-score">{job['fit_score']}%</span>
                </div>
                <div class="job-meta">
                    <span class="company">{job['company']}</span>
                    <span class="location">{job['location']}</span>
                    <span class="source">{job.get('source', 'Unknown')}</span>
                </div>
                {cap_exempt_badge}
                <div class="tech-match">Tech Stack Match: {job.get('tech_stack_match', 'N/A')}%</div>
                <div class="experience-match">Experience: {job.get('experience_match', 'N/A')}</div>
                
                <div class="strengths">
                    <h4>✅ Strengths:</h4>
                    <ul>{strengths_html}</ul>
                </div>
                
                <div class="gaps">
                    <h4>⚠️ Gaps to Address:</h4>
                    <ul>{gaps_html}</ul>
                </div>
                
                <div class="reasoning">
                    <p><strong>Reasoning:</strong> {job.get('reasoning', 'No reasoning provided')}</p>
                </div>
                
                <div class="actions">
                    <a href="{job['job_url']}" 
                       class="apply-link" 
                       target="_blank"
                       onclick="markAsClicked(this, 'job_{i}')">
                       View Job & Apply
                    </a>
                    <a href="applications/{company_safe}_resume.docx" class="doc-link">Resume</a>
                    <a href="applications/{company_safe}_cover_letter.txt" class="doc-link">Cover Letter</a>
                </div>
            </div>
            """
        
        # Complete HTML
        html = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Job Search Tracker - Mohamad Abboud</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            background: #f5f5f5;
            color: #333;
            line-height: 1.6;
        }}
        
        header {{
            background: #2c3e50;
            color: white;
            padding: 2rem;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        
        header h1 {{
            margin-bottom: 1rem;
        }}
        
        .stats {{
            margin-bottom: 1rem;
            font-size: 1.1rem;
        }}
        
        .filters {{
            display: flex;
            gap: 0.5rem;
            flex-wrap: wrap;
        }}
        
        .filters button {{
            padding: 0.5rem 1rem;
            border: none;
            background: #34495e;
            color: white;
            cursor: pointer;
            border-radius: 4px;
            transition: background 0.3s;
        }}
        
        .filters button:hover {{
            background: #1abc9c;
        }}
        
        .job-cards {{
            max-width: 1200px;
            margin: 2rem auto;
            padding: 0 1rem;
        }}
        
        .job-card {{
            background: white;
            border-radius: 8px;
            padding: 1.5rem;
            margin-bottom: 1.5rem;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            border-left: 5px solid #ccc;
            transition: transform 0.2s, box-shadow 0.2s;
        }}
        
        .job-card:hover {{
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        }}
        
        .job-card.excellent {{
            border-left-color: #27ae60;
        }}
        
        .job-card.good {{
            border-left-color: #3498db;
        }}
        
        .job-card.borderline {{
            border-left-color: #f39c12;
        }}
        
        .job-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 1rem;
            padding-bottom: 1rem;
            border-bottom: 2px solid #ecf0f1;
        }}
        
        .job-header h2 {{
            font-size: 1.4rem;
            color: #2c3e50;
        }}
        
        .fit-score {{
            font-size: 1.8rem;
            font-weight: bold;
            color: #27ae60;
        }}
        
        .job-meta {{
            display: flex;
            gap: 1rem;
            margin-bottom: 1rem;
            flex-wrap: wrap;
        }}
        
        .job-meta span {{
            padding: 0.25rem 0.75rem;
            background: #ecf0f1;
            border-radius: 4px;
            font-size: 0.9rem;
        }}
        
        .company {{
            background: #3498db !important;
            color: white;
        }}
        
        .cap-exempt-badge {{
            display: inline-block;
            padding: 0.5rem 1rem;
            background: #27ae60;
            color: white;
            border-radius: 4px;
            margin-bottom: 1rem;
            font-weight: bold;
        }}
        
        .cap-exempt-badge.unknown {{
            background: #e67e22;
        }}
        
        .cap-exempt-badge.no {{
            background: #e74c3c;
        }}
        
        .tech-match, .experience-match {{
            margin-bottom: 0.5rem;
            font-weight: 500;
        }}
        
        .strengths, .gaps {{
            margin: 1rem 0;
        }}
        
        .strengths h4 {{
            color: #27ae60;
            margin-bottom: 0.5rem;
        }}
        
        .gaps h4 {{
            color: #e67e22;
            margin-bottom: 0.5rem;
        }}
        
        .strengths ul, .gaps ul {{
            list-style-position: inside;
            padding-left: 1rem;
        }}
        
        .strengths li, .gaps li {{
            margin-bottom: 0.25rem;
        }}
        
        .reasoning {{
            background: #f8f9fa;
            padding: 1rem;
            border-radius: 4px;
            margin: 1rem 0;
        }}
        
        .actions {{
            display: flex;
            gap: 1rem;
            margin-top: 1rem;
            flex-wrap: wrap;
        }}
        
        .apply-link {{
            padding: 0.75rem 1.5rem;
            background: #27ae60;
            color: white;
            text-decoration: none;
            border-radius: 4px;
            font-weight: bold;
            transition: background 0.3s;
        }}
        
        .apply-link:hover {{
            background: #229954;
        }}
        
        .apply-link.visited {{
            background: #95a5a6;
            text-decoration: line-through;
        }}
        
        .doc-link {{
            padding: 0.75rem 1.5rem;
            background: #3498db;
            color: white;
            text-decoration: none;
            border-radius: 4px;
            transition: background 0.3s;
        }}
        
        .doc-link:hover {{
            background: #2980b9;
        }}
        
        @media print {{
            .filters, .actions {{
                display: none;
            }}
            
            .job-card {{
                page-break-inside: avoid;
            }}
        }}
        
        @media (max-width: 768px) {{
            .job-header {{
                flex-direction: column;
                align-items: flex-start;
            }}
            
            .fit-score {{
                margin-top: 0.5rem;
            }}
        }}
    </style>
</head>
<body>
    <header>
        <h1>🎯 Job Applications Tracker</h1>
        <div class="stats">
            Total Jobs: {len(jobs)} | 
            Excellent: {excellent} | 
            Good: {good} | 
            Borderline: {borderline} | 
            Applied: <span id="applied-count">0</span>
        </div>
        <div class="filters">
            <button onclick="filterBy('all')">Show All</button>
            <button onclick="filterBy('excellent')">Excellent Only</button>
            <button onclick="filterBy('good')">Good Only</button>
            <button onclick="filterBy('borderline')">Borderline Only</button>
            <button onclick="filterBy('not-applied')">Not Applied</button>
            <button onclick="clearClicked()">Reset Applied Status</button>
        </div>
        <p style="margin-top: 1rem; font-size: 0.9rem;">Last updated: {datetime.now().strftime('%B %d, %Y at %I:%M %p')}</p>
    </header>
    
    <div class="job-cards">
        {job_cards_html}
    </div>
    
    <script>
        // Track clicked links in localStorage
        function markAsClicked(element, jobId) {{
            let clicked = JSON.parse(localStorage.getItem('clickedJobs') || '[]');
            if (!clicked.includes(jobId)) {{
                clicked.push(jobId);
                localStorage.setItem('clickedJobs', JSON.stringify(clicked));
            }}
            element.classList.add('visited');
            updateStats();
        }}
        
        // Load clicked state on page load
        window.onload = function() {{
            let clicked = JSON.parse(localStorage.getItem('clickedJobs') || '[]');
            clicked.forEach(jobId => {{
                let link = document.querySelector(`[onclick*="${{jobId}}"]`);
                if (link) link.classList.add('visited');
            }});
            updateStats();
        }};
        
        // Filter functionality
        function filterBy(category) {{
            let cards = document.querySelectorAll('.job-card');
            cards.forEach(card => {{
                if (category === 'all') {{
                    card.style.display = 'block';
                }} else if (category === 'not-applied') {{
                    let link = card.querySelector('.apply-link');
                    card.style.display = link.classList.contains('visited') ? 'none' : 'block';
                }} else {{
                    card.style.display = card.classList.contains(category) ? 'block' : 'none';
                }}
            }});
        }}
        
        function updateStats() {{
            let clicked = JSON.parse(localStorage.getItem('clickedJobs') || '[]');
            document.getElementById('applied-count').textContent = clicked.length;
        }}
        
        function clearClicked() {{
            if (confirm('Are you sure you want to reset all applied statuses?')) {{
                localStorage.removeItem('clickedJobs');
                location.reload();
            }}
        }}
    </script>
</body>
</html>
        """
        
        # Save HTML file
        with open(f"{config.OUTPUT_DIR}/tracker.html", 'w') as f:
            f.write(html)
        
        logger.info(f"Generated tracker with {len(jobs)} jobs")
        
        return html
    
    def get_category_class(self, fit_score):
        """Get CSS class for fit category"""
        if fit_score >= config.EXCELLENT_THRESHOLD:
            return "excellent"
        elif fit_score >= config.GOOD_THRESHOLD:
            return "good"
        else:
            return "borderline"
    
    def get_cap_exempt_badge(self, job):
        """Generate cap-exempt status badge"""
        cap_exempt = job.get('cap_exempt_verified', None)
        
        if cap_exempt == True:
            return '<div class="cap-exempt-badge">✅ Cap-Exempt Verified</div>'
        elif cap_exempt == False:
            return '<div class="cap-exempt-badge no">❌ NOT Cap-Exempt</div>'
        else:
            return '<div class="cap-exempt-badge unknown">⚠️ Cap-Exempt Status Unknown</div>'
```

---

### 9. Main Orchestrator (main.py)

```python
import asyncio
import schedule
import time
import logging
import os
from datetime import datetime
from src.scraper import JobScraper
from src.evaluator import JobEvaluator
from src.resume_generator import ResumeGenerator
from src.cover_letter_gen import CoverLetterGenerator
from src.tracker import TrackerGenerator
import config

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'{config.LOGS_DIR}/search_log.txt'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Initialize components
scraper = JobScraper()
evaluator = JobEvaluator()
resume_gen = ResumeGenerator()
cover_gen = CoverLetterGenerator()
tracker_gen = TrackerGenerator()

async def run_job_search_cycle():
    """Main job search workflow"""
    try:
        logger.info("=" * 80)
        logger.info(f"Starting job search cycle at {datetime.now()}")
        logger.info("=" * 80)
        
        # 1. Discover new jobs
        logger.info("Step 1: Searching job boards...")
        new_jobs = await scraper.search_job_boards()
        logger.info(f"Found {len(new_jobs)} new job postings")
        
        if not new_jobs:
            logger.info("No new jobs found. Ending cycle.")
            return
        
        # 2. Extract full content and verify cap-exempt status
        logger.info("Step 2: Extracting job details and verifying cap-exempt status...")
        jobs_with_content = []
        
        for i, job in enumerate(new_jobs):
            logger.info(f"Processing job {i+1}/{len(new_jobs)}: {job['title']} at {job['company']}")
            
            # Extract content
            content = await scraper.extract_job_content(job)
            if not content:
                logger.warning(f"Failed to extract content for {job['title']}")
                continue
            
            # Verify cap-exempt
            cap_exempt = await scraper.verify_cap_exempt_employer(job['company'])
            content['cap_exempt'] = cap_exempt
            
            jobs_with_content.append(content)
            
            # Rate limiting
            await asyncio.sleep(config.REQUEST_DELAY)
        
        logger.info(f"Successfully extracted {len(jobs_with_content)} job details")
        
        # 3. Evaluate with Claude
        logger.info("Step 3: Evaluating jobs with Claude API...")
        evaluations = await evaluator.batch_evaluate_jobs(jobs_with_content)
        
        # 4. Filter: Keep only APPLY recommendations with fit >= 50
        good_jobs = [
            j for j in evaluations 
            if j and j.get('recommendation') == 'APPLY' and j.get('fit_score', 0) >= config.BORDERLINE_THRESHOLD
        ]
        logger.info(f"{len(good_jobs)} jobs passed evaluation and are worth applying to")
        
        if not good_jobs:
            logger.info("No jobs met the criteria. Ending cycle.")
            # Still update tracker with all evaluations
            tracker_gen.generate_tracker_html(evaluations)
            return
        
        # 5. Generate tailored resumes & cover letters
        logger.info("Step 4: Generating tailored application materials...")
        
        for i, job in enumerate(good_jobs):
            logger.info(f"Generating materials for {i+1}/{len(good_jobs)}: {job['company']}")
            
            try:
                # Generate resume
                resume_md = await resume_gen.generate_ats_resume(job, evaluator.master_resume)
                if resume_md:
                    resume_gen.convert_to_docx(resume_md, job['company'])
                
                # Generate cover letter
                await cover_gen.generate_cover_letter(job)
                
            except Exception as e:
                logger.error(f"Error generating materials for {job['company']}: {e}")
                continue
        
        # 6. Update HTML tracker
        logger.info("Step 5: Updating HTML tracker...")
        tracker_gen.generate_tracker_html(evaluations)
        
        logger.info("=" * 80)
        logger.info(f"Cycle complete! Found {len(good_jobs)} jobs worth applying to.")
        logger.info(f"Check {config.OUTPUT_DIR}/tracker.html for results")
        logger.info("=" * 80)
        
    except Exception as e:
        logger.error(f"Error in job search cycle: {e}", exc_info=True)

def run_cycle_sync():
    """Synchronous wrapper for scheduling"""
    asyncio.run(run_job_search_cycle())

def setup_directories():
    """Create necessary directories"""
    dirs = [
        config.DATA_DIR,
        config.OUTPUT_DIR,
        config.APPLICATIONS_DIR,
        config.LOGS_DIR
    ]
    for d in dirs:
        os.makedirs(d, exist_ok=True)

def run_scheduler():
    """Run autonomous scheduler"""
    logger.info("Starting autonomous job search scheduler...")
    logger.info(f"Will run every {config.SEARCH_INTERVAL_HOURS} hours")
    logger.info(f"Also scheduled for: {', '.join(config.SEARCH_TIMES)}")
    
    # Schedule periodic runs
    schedule.every(config.SEARCH_INTERVAL_HOURS).hours.do(run_cycle_sync)
    
    # Schedule specific times
    for time_str in config.SEARCH_TIMES:
        schedule.every().day.at(time_str).do(run_cycle_sync)
    
    # Run immediately on start
    run_cycle_sync()
    
    # Keep running
    while True:
        schedule.run_pending()
        time.sleep(60)  # Check every minute

if __name__ == "__main__":
    setup_directories()
    
    # Check for API key
    if not config.ANTHROPIC_API_KEY:
        logger.error("ANTHROPIC_API_KEY not set in environment variables!")
        logger.error("Please set it with: export ANTHROPIC_API_KEY='your-key-here'")
        exit(1)
    
    # Choose mode
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--once":
        # Run once and exit
        logger.info("Running single search cycle...")
        asyncio.run(run_job_search_cycle())
    else:
        # Run scheduler (autonomous mode)
        run_scheduler()
```

---

### 10. Environment Setup (.env file)

Create `.env` file:
```
ANTHROPIC_API_KEY=your_api_key_here
USAJOBS_API_KEY=your_usajobs_key_here
```

---

## Deployment Instructions

### 11. Quick Start

```bash
# 1. Clone or create project
mkdir job-search-agent
cd job-search-agent

# 2. Set up environment
export ANTHROPIC_API_KEY="your_key_here"

# 3. Install dependencies
pip install -r requirements.txt --break-system-packages

# 4. Run once to test
python main.py --once

# 5. Run autonomous scheduler
python main.py
```

### 12. Run as Background Service

**Option A: Using nohup (simple)**
```bash
nohup python main.py > logs/background.log 2>&1 &
```

**Option B: Using systemd (Linux)**
Create `/etc/systemd/system/job-search.service`:
```ini
[Unit]
Description=Job Search Agent
After=network.target

[Service]
Type=simple
User=your_username
WorkingDirectory=/path/to/job-search-agent
Environment="ANTHROPIC_API_KEY=your_key"
ExecStart=/usr/bin/python3 main.py
Restart=always

[Install]
WantedBy=multi-user.target
```

Then:
```bash
sudo systemctl enable job-search
sudo systemctl start job-search
sudo systemctl status job-search
```

**Option C: Using cron**
```bash
# Run every 6 hours
0 */6 * * * cd /path/to/job-search-agent && /usr/bin/python3 main.py --once >> logs/cron.log 2>&1
```

---

## Expected Outputs

### 13. Files Generated

After each cycle, you'll have:

```
output/
├── tracker.html                          # Interactive tracker
└── applications/
    ├── Vanderbilt_University_resume.docx
    ├── Vanderbilt_University_cover_letter.txt
    ├── City_of_Fresno_resume.docx
    ├── City_of_Fresno_cover_letter.txt
    └── ...

data/
├── jobs_found.json                       # All jobs discovered
└── jobs_evaluated.json                   # Evaluation results

logs/
├── search_log.txt                        # Activity log
└── errors.log                            # Error tracking
```

---

## Monitoring & Maintenance

### 14. Check Progress

```bash
# View logs
tail -f logs/search_log.txt

# Check tracker
open output/tracker.html

# See latest evaluations
cat data/jobs_evaluated.json | jq '.[-5:]'
```

### 15. Adjust Search Parameters

Edit `config.py` to:
- Add new search queries
- Adjust fit score thresholds
- Change search frequency
- Update cap-exempt indicators

---

## Advanced Features (Optional Enhancements)

### 16. Email Notifications

Add to main.py:
```python
import smtplib
from email.mime.text import MIMEText

def send_daily_digest(good_jobs):
    """Send email with new good jobs"""
    msg = MIMEText(f"Found {len(good_jobs)} new jobs worth applying to!")
    msg['Subject'] = f'Job Alert: {len(good_jobs)} New Opportunities'
    msg['From'] = 'your_email@gmail.com'
    msg['To'] = 'mohammad.a.abboud@gmail.com'
    
    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
        smtp.login('your_email@gmail.com', 'app_password')
        smtp.send_message(msg)
```

### 17. Analytics Dashboard

Track metrics over time:
- Jobs found per day
- Average fit scores
- Most successful search queries
- Cap-exempt verification accuracy

---

## Troubleshooting

### 18. Common Issues

**Issue: API rate limits**
- Solution: Increase delays in config.py

**Issue: Job boards blocking scraper**
- Solution: Add more user agents, use proxies, or switch to official APIs

**Issue: Cap-exempt verification inaccurate**
- Solution: Build manual verified list, use MyVisaJobs API

**Issue: Resumes not ATS-friendly**
- Solution: Adjust prompt, test with Jobscan.co

---

## Success Metrics

After 1 week, you should have:
- 50-100+ jobs discovered
- 10-20 high-quality applications ready
- HTML tracker with all opportunities
- Tailored resumes and cover letters for each

---

## Total Implementation Time

**6-8 hours for Claude Code to build complete system**

---

## Ready to Execute!

Give this full markdown file to Claude Code and say:

> "Please implement this entire job search agent system following these instructions. Create all files, test each component, and ensure the autonomous scheduler works correctly. Focus on making it robust and production-ready."

**Good luck with your job search, Mohamad! 🚀**
