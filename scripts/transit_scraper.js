/**
 * Transit Agency IT Job Scraper
 * Uses Playwright to visit each portal and collect IT/software/data job listings.
 */

const { chromium } = require('/opt/node22/lib/node_modules/playwright');
const fs = require('fs');
const path = require('path');

const SCREENSHOT_DIR = '/home/user/Agents2/output/screenshots';
const RESULTS_FILE = '/home/user/Agents2/output/transit_it_jobs.json';

if (!fs.existsSync(SCREENSHOT_DIR)) fs.mkdirSync(SCREENSHOT_DIR, { recursive: true });

const IT_KEYWORDS = [
  'software', 'developer', 'engineer', 'data', 'IT', 'information technology',
  'database', 'analyst', 'programmer', 'python', 'full stack', 'backend',
  'application', 'systems', 'infrastructure', 'devops', 'cloud', 'cybersecurity',
  'network', 'technical', 'technology', 'web', 'digital', 'platform', 'integration',
  'ETL', 'architect', '.NET', 'java', 'SQL', 'GIS', 'reporting', 'analytics',
  'support analyst', 'solutions', 'ERP', 'SAP', 'oracle', 'salesforce'
];

function isITJob(title) {
  const t = title.toLowerCase();
  return IT_KEYWORDS.some(k => t.includes(k.toLowerCase()));
}

const portals = [
  {
    name: 'Sound Transit',
    url: 'https://recruiting.ultipro.com/SOU1036SOUND/JobBoard/dcc5dbea-875e-4cd1-bfd2-8e046cecc54f/',
    type: 'ultipro'
  },
  {
    name: 'RTD Denver',
    url: 'https://rtddenver.wd5.myworkdayjobs.com/Careers',
    type: 'workday'
  },
  {
    name: 'CapMetro Austin',
    url: 'https://capmetro.wd1.myworkdayjobs.com/capmetro',
    type: 'workday'
  },
  {
    name: 'MARTA Atlanta',
    url: 'https://fa-evii-saasfaprod1.fa.ocs.oraclecloud.com/hcmUI/CandidateExperience/en/sites/CX_1',
    type: 'oracle'
  },
  {
    name: 'WMATA DC',
    url: 'https://careers.wmata.com',
    type: 'wmata'
  },
  {
    name: 'VTA Santa Clara',
    url: 'https://www.governmentjobs.com/careers/vtasantaclara',
    type: 'governmentjobs'
  },
  {
    name: 'NJ Transit',
    url: 'https://careers.smartrecruiters.com/NJTransit/',
    type: 'smartrecruiters'
  },
  {
    name: 'MTA New York',
    url: 'https://careers.mta.info',
    type: 'mta'
  },
  {
    name: 'SEPTA Philadelphia',
    url: 'https://www.septa.org/careers',
    type: 'septa'
  },
  {
    name: 'King County Metro',
    url: 'https://www.governmentjobs.com/careers/kingcountywa',
    type: 'governmentjobs'
  },
  {
    name: 'BART',
    url: 'https://www.governmentjobs.com/careers/bartca',
    type: 'governmentjobs'
  },
  {
    name: 'LA Metro',
    url: 'https://www.governmentjobs.com/careers/lametro',
    type: 'governmentjobs'
  },
  {
    name: 'TriMet Portland',
    url: 'https://www.governmentjobs.com/careers/trimet',
    type: 'governmentjobs'
  },
  {
    name: 'Pace Suburban Bus',
    url: 'https://iaymqy.fa.ocs.oraclecloud.com/hcmUI/CandidateExperience/en/sites/CX_1',
    type: 'oracle'
  },
  {
    name: 'COTA Columbus',
    url: 'https://www.cota.com/careers/',
    type: 'cota'
  }
];

async function delay(ms) {
  return new Promise(r => setTimeout(r, ms));
}

async function scrapeGovernmentJobs(page, portal) {
  const jobs = [];
  try {
    await page.goto(portal.url, { waitUntil: 'networkidle', timeout: 30000 });
    await delay(2000);
    await page.screenshot({ path: `${SCREENSHOT_DIR}/${portal.name.replace(/\s+/g,'_')}_1.png`, fullPage: false });

    // Try searching for IT keywords
    const searchTerms = ['software', 'information technology', 'data', 'engineer', 'developer', 'IT'];

    for (const term of searchTerms) {
      try {
        // Look for search input
        const searchInput = await page.$('input[placeholder*="search" i], input[name*="keyword" i], input[id*="keyword" i], input[type="search"]');
        if (searchInput) {
          await searchInput.triple_click();
          await searchInput.fill(term);
          await page.keyboard.press('Enter');
          await delay(2000);
        } else {
          // Navigate with search param
          const searchUrl = `${portal.url}?keyword=${encodeURIComponent(term)}`;
          await page.goto(searchUrl, { waitUntil: 'networkidle', timeout: 25000 });
          await delay(2000);
        }

        // Collect job listings
        const listings = await page.$$eval(
          'a[href*="/careers/"][href*="job"]',
          (links) => links.map(l => ({ title: l.textContent.trim(), url: l.href })).filter(j => j.title.length > 3)
        );

        for (const job of listings) {
          if (isITJob(job.title) && !jobs.find(j => j.url === job.url)) {
            jobs.push(job);
          }
        }
      } catch (e) {
        // continue to next term
      }
    }

    // Also grab all jobs from listing page
    try {
      const baseJobsUrl = `${portal.url}?keyword=&department=Information+Technology`;
      await page.goto(baseJobsUrl, { waitUntil: 'networkidle', timeout: 25000 });
      await delay(2000);

      const allListings = await page.$$eval(
        'a.job-title, a[class*="title"], h2 a, h3 a, td a, .job-list a',
        (links) => links.map(l => ({ title: l.textContent.trim(), url: l.href })).filter(j => j.title.length > 3)
      );
      for (const job of allListings) {
        if (isITJob(job.title) && !jobs.find(j => j.url === job.url)) {
          jobs.push(job);
        }
      }
    } catch(e) {}

  } catch (e) {
    console.error(`Error scraping ${portal.name}:`, e.message);
  }
  return jobs;
}

async function scrapeWorkday(page, portal) {
  const jobs = [];
  try {
    await page.goto(portal.url, { waitUntil: 'networkidle', timeout: 30000 });
    await delay(3000);
    await page.screenshot({ path: `${SCREENSHOT_DIR}/${portal.name.replace(/\s+/g,'_')}_1.png`, fullPage: false });

    // Try searching
    const searchTerms = ['software engineer', 'information technology', 'data engineer', 'developer'];

    for (const term of searchTerms) {
      try {
        await page.goto(portal.url, { waitUntil: 'networkidle', timeout: 25000 });
        await delay(2000);

        // Find search input in workday
        const searchInput = await page.$('input[data-automation-id="searchBox"], input[placeholder*="Search" i], input[aria-label*="search" i]');
        if (searchInput) {
          await searchInput.click();
          await searchInput.fill(term);
          await page.keyboard.press('Enter');
          await delay(3000);

          // Collect results
          const listings = await page.$$eval(
            'a[data-automation-id="jobTitle"], h2 a, h3 a, .css-1q2dra3 a, [class*="jobTitle"] a',
            (links) => links.map(l => ({ title: l.textContent.trim(), url: l.href })).filter(j => j.title.length > 3)
          );
          for (const job of listings) {
            if (isITJob(job.title) && !jobs.find(j => j.url === job.url)) {
              jobs.push(job);
            }
          }
        }
      } catch(e) {}
    }

    // Also try all jobs and filter
    try {
      const allJobLinks = await page.$$eval(
        'a[data-automation-id="jobTitle"], li a, .WDUI-table a',
        (links) => links.map(l => ({ title: l.textContent.trim(), url: l.href })).filter(j => j.title.length > 3)
      );
      for (const job of allJobLinks) {
        if (isITJob(job.title) && !jobs.find(j => j.url === job.url)) {
          jobs.push(job);
        }
      }
    } catch(e) {}

  } catch (e) {
    console.error(`Error scraping ${portal.name}:`, e.message);
  }
  return jobs;
}

async function scrapeUltipro(page, portal) {
  const jobs = [];
  try {
    await page.goto(portal.url, { waitUntil: 'networkidle', timeout: 30000 });
    await delay(3000);
    await page.screenshot({ path: `${SCREENSHOT_DIR}/${portal.name.replace(/\s+/g,'_')}_1.png`, fullPage: false });

    // Get all job listings
    const allLinks = await page.$$eval(
      'a[href*="JobDetail"], a[href*="job"], h2 a, h3 a, td a, .opportunity-list a, .job-title a',
      (links) => links.map(l => ({ title: l.textContent.trim(), url: l.href })).filter(j => j.title.length > 3)
    );
    for (const job of allLinks) {
      if (isITJob(job.title) && !jobs.find(j => j.url === job.url)) {
        jobs.push(job);
      }
    }

    // Search for IT
    try {
      const searchInput = await page.$('input[type="text"], input[placeholder*="search" i], input[name*="keyword" i]');
      if (searchInput) {
        await searchInput.fill('information technology');
        await page.keyboard.press('Enter');
        await delay(2000);

        const moreLinks = await page.$$eval(
          'a[href*="JobDetail"], a[href*="job"], h2 a, h3 a, td a',
          (links) => links.map(l => ({ title: l.textContent.trim(), url: l.href })).filter(j => j.title.length > 3)
        );
        for (const job of moreLinks) {
          if (isITJob(job.title) && !jobs.find(j => j.url === job.url)) {
            jobs.push(job);
          }
        }
      }
    } catch(e) {}

  } catch (e) {
    console.error(`Error scraping ${portal.name}:`, e.message);
  }
  return jobs;
}

async function scrapeOracle(page, portal) {
  const jobs = [];
  try {
    await page.goto(portal.url, { waitUntil: 'networkidle', timeout: 30000 });
    await delay(3000);
    await page.screenshot({ path: `${SCREENSHOT_DIR}/${portal.name.replace(/\s+/g,'_')}_1.png`, fullPage: false });

    // Oracle HCM - look for job links
    const allLinks = await page.$$eval(
      'a[href*="job"], a[data-bind*="job"], a[class*="job"], h2 a, h3 a, h4 a, li a',
      (links) => links.map(l => ({ title: l.textContent.trim(), url: l.href })).filter(j => j.title.length > 3 && j.title.length < 200)
    );
    for (const job of allLinks) {
      if (isITJob(job.title) && !jobs.find(j => j.url === job.url)) {
        jobs.push(job);
      }
    }

    // Try search
    try {
      const searchInput = await page.$('input[placeholder*="keyword" i], input[placeholder*="search" i], input[type="search"]');
      if (searchInput) {
        await searchInput.fill('information technology');
        await page.keyboard.press('Enter');
        await delay(3000);

        const moreLinks = await page.$$eval(
          'a[href*="job"], a[data-bind*="job"], h2 a, h3 a, li a',
          (links) => links.map(l => ({ title: l.textContent.trim(), url: l.href })).filter(j => j.title.length > 3 && j.title.length < 200)
        );
        for (const job of moreLinks) {
          if (isITJob(job.title) && !jobs.find(j => j.url === job.url)) {
            jobs.push(job);
          }
        }
      }
    } catch(e) {}

  } catch (e) {
    console.error(`Error scraping ${portal.name}:`, e.message);
  }
  return jobs;
}

async function scrapeGeneric(page, portal) {
  const jobs = [];
  try {
    await page.goto(portal.url, { waitUntil: 'networkidle', timeout: 30000 });
    await delay(3000);
    await page.screenshot({ path: `${SCREENSHOT_DIR}/${portal.name.replace(/\s+/g,'_')}_1.png`, fullPage: false });

    // Generic: grab all links that look like job postings
    const allLinks = await page.$$eval(
      'a',
      (links) => links.map(l => ({ title: l.textContent.trim(), url: l.href }))
        .filter(j => j.title.length > 5 && j.title.length < 150 && j.url.length > 10)
    );
    for (const job of allLinks) {
      if (isITJob(job.title) && !jobs.find(j => j.url === job.url)) {
        jobs.push(job);
      }
    }

    // Try page text for job titles near links
    const pageText = await page.textContent('body');
    console.log(`  Page text length: ${pageText.length} chars`);

  } catch (e) {
    console.error(`Error scraping ${portal.name}:`, e.message);
  }
  return jobs;
}

async function scrapeSmartRecruiters(page, portal) {
  const jobs = [];
  try {
    await page.goto(portal.url, { waitUntil: 'networkidle', timeout: 30000 });
    await delay(3000);
    await page.screenshot({ path: `${SCREENSHOT_DIR}/${portal.name.replace(/\s+/g,'_')}_1.png`, fullPage: false });

    const searchTerms = ['software', 'information technology', 'data', 'IT analyst'];
    for (const term of searchTerms) {
      try {
        const searchUrl = `${portal.url}?search=${encodeURIComponent(term)}`;
        await page.goto(searchUrl, { waitUntil: 'networkidle', timeout: 25000 });
        await delay(2000);

        const allLinks = await page.$$eval(
          'a[href*="/NJTransit/"], a.job-list-item, li a, h2 a, h3 a, [class*="job"] a',
          (links) => links.map(l => ({ title: l.textContent.trim(), url: l.href })).filter(j => j.title.length > 3 && j.title.length < 200)
        );
        for (const job of allLinks) {
          if (isITJob(job.title) && !jobs.find(j => j.url === job.url)) {
            jobs.push(job);
          }
        }
      } catch(e) {}
    }
  } catch (e) {
    console.error(`Error scraping ${portal.name}:`, e.message);
  }
  return jobs;
}

async function main() {
  const browser = await chromium.launch({
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage']
  });

  const context = await browser.newContext({
    userAgent: 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    viewport: { width: 1280, height: 800 }
  });

  const allResults = [];

  for (const portal of portals) {
    console.log(`\n=== Scraping ${portal.name} (${portal.type}) ===`);
    const page = await context.newPage();

    let jobs = [];
    try {
      switch(portal.type) {
        case 'governmentjobs':
          jobs = await scrapeGovernmentJobs(page, portal);
          break;
        case 'workday':
          jobs = await scrapeWorkday(page, portal);
          break;
        case 'ultipro':
          jobs = await scrapeUltipro(page, portal);
          break;
        case 'oracle':
          jobs = await scrapeOracle(page, portal);
          break;
        case 'smartrecruiters':
          jobs = await scrapeSmartRecruiters(page, portal);
          break;
        default:
          jobs = await scrapeGeneric(page, portal);
          break;
      }
    } catch(e) {
      console.error(`Fatal error for ${portal.name}:`, e.message);
    }

    await page.close();

    console.log(`  Found ${jobs.length} IT job(s) for ${portal.name}`);
    jobs.forEach(j => console.log(`    - ${j.title} | ${j.url}`));

    allResults.push({
      agency: portal.name,
      url: portal.url,
      jobs: jobs
    });
  }

  await browser.close();

  fs.writeFileSync(RESULTS_FILE, JSON.stringify(allResults, null, 2));
  console.log(`\n\nResults saved to ${RESULTS_FILE}`);

  // Print summary
  console.log('\n\n=== SUMMARY ===');
  let totalJobs = 0;
  for (const r of allResults) {
    console.log(`\n${r.agency}: ${r.jobs.length} IT job(s)`);
    r.jobs.forEach(j => console.log(`  - ${j.title}`));
    totalJobs += r.jobs.length;
  }
  console.log(`\nTotal IT jobs found: ${totalJobs}`);
}

main().catch(console.error);
