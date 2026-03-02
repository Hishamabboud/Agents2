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

            logger.info(
                f"Evaluated {job_data['title']} at {job_data['company']}: "
                f"{evaluation['fit_score']}% - {evaluation['recommendation']}"
            )

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
