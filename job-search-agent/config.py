import os
from dotenv import load_dotenv

load_dotenv()

# API Configuration
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
USAJOBS_API_KEY = os.getenv("USAJOBS_API_KEY", "")
CLAUDE_MODEL = "claude-sonnet-4-20250514"

# User Agent
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

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
