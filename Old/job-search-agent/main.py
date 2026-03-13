import asyncio
import schedule
import time
import logging
import os
import sys
from datetime import datetime
from src.scraper import JobScraper
from src.evaluator import JobEvaluator
from src.resume_generator import ResumeGenerator
from src.cover_letter_gen import CoverLetterGenerator
from src.tracker import TrackerGenerator
import config

# Setup logging
os.makedirs(config.LOGS_DIR, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'{config.LOGS_DIR}/search_log.txt'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


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


async def run_job_search_cycle():
    """Main job search workflow"""
    # Initialize components inside the async function to avoid issues
    scraper = JobScraper()
    evaluator = JobEvaluator()
    resume_gen = ResumeGenerator()
    cover_gen = CoverLetterGenerator()
    tracker_gen = TrackerGenerator()

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
        sys.exit(1)

    # Choose mode
    if len(sys.argv) > 1 and sys.argv[1] == "--once":
        # Run once and exit
        logger.info("Running single search cycle...")
        asyncio.run(run_job_search_cycle())
    else:
        # Run scheduler (autonomous mode)
        run_scheduler()
