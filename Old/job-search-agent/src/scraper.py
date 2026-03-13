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
        chrome_options.add_argument(
            "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        )

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

        # Save discovered jobs
        self.save_jobs(unique_jobs)

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
                        anchor = title_elem.find('a')
                        if not anchor:
                            continue
                        job_url = "https://www.indeed.com" + anchor['href']

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
                'Authorization-Key': config.USAJOBS_API_KEY
            }
            params = {
                'Keyword': query,
                'ResultsPerPage': 20
            }

            response = requests.get(api_url, headers=headers, params=params, timeout=10)
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

    def save_jobs(self, new_jobs):
        """Append newly discovered jobs to jobs_found.json"""
        try:
            try:
                with open(f"{config.DATA_DIR}/jobs_found.json", 'r') as f:
                    existing = json.load(f)
            except FileNotFoundError:
                existing = []

            existing.extend(new_jobs)

            with open(f"{config.DATA_DIR}/jobs_found.json", 'w') as f:
                json.dump(existing, f, indent=2)

            logger.info(f"Saved {len(new_jobs)} new jobs to jobs_found.json")
        except Exception as e:
            logger.error(f"Error saving jobs: {e}")

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
            response = requests.get(search_url, headers=headers, timeout=10)

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
