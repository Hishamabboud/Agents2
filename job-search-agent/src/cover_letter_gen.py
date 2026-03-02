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
            response = requests.get(search_url, headers=headers, timeout=10)

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
                        snippet = text[max(0, idx - 100):min(len(text), idx + 200)]
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
            safe_name = job_evaluation['company'].replace(' ', '_').replace('/', '_').replace('\\', '_')
            filename = f"{config.APPLICATIONS_DIR}/{safe_name}_cover_letter.txt"
            with open(filename, 'w') as f:
                f.write(cover_letter)

            logger.info(f"Generated cover letter: {filename}")

            return cover_letter

        except Exception as e:
            logger.error(f"Error generating cover letter: {e}")
            return None
