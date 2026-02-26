# Manual Jobs Directory
#
# How to use:
#   1. When a job fails to scrape, a stub file is created in data/failed-scrapes/
#   2. Open the stub, visit the URL in your browser, and copy the job posting
#   3. Fill in TITLE, COMPANY, SALARY, and paste the full description
#   4. Move or copy the filled-in file into THIS folder (data/manual-jobs/)
#   5. Re-run the pipeline — search.py will pick up the file automatically
#
# File format (copy from any stub in failed-scrapes/):
#
# # URL: https://original-job-url-here
# # REASON: why it failed
#
# TITLE: Senior Software Engineer
# COMPANY: Acme Corp
# SALARY: $100,000 - $130,000
#
# --- JOB DESCRIPTION ---
# <paste full job description here>
#
# Notes:
#   - The "# URL:" line is required so the pipeline can deduplicate correctly
#   - Files already processed will be skipped on subsequent runs
#   - This README file is ignored by the pipeline
