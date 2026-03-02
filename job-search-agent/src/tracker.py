import json
from datetime import datetime
import config
import logging

logger = logging.getLogger(__name__)


class TrackerGenerator:
    def generate_tracker_html(self, evaluated_jobs):
        """Generate interactive HTML tracker"""

        # Sort jobs by fit score
        jobs = sorted(evaluated_jobs, key=lambda x: x.get('fit_score', 0), reverse=True)

        # Count by category
        excellent = len([j for j in jobs if j.get('fit_score', 0) >= config.EXCELLENT_THRESHOLD])
        good = len([j for j in jobs if config.GOOD_THRESHOLD <= j.get('fit_score', 0) < config.EXCELLENT_THRESHOLD])
        borderline = len([j for j in jobs if config.BORDERLINE_THRESHOLD <= j.get('fit_score', 0) < config.GOOD_THRESHOLD])

        # Generate job cards HTML
        job_cards_html = ""
        for i, job in enumerate(jobs):
            if job.get('recommendation') != 'APPLY':
                continue

            category = self.get_category_class(job.get('fit_score', 0))
            cap_exempt_badge = self.get_cap_exempt_badge(job)

            strengths_html = "".join([f"<li>{s}</li>" for s in job.get('strengths', [])])
            gaps_html = "".join([f"<li>{g}</li>" for g in job.get('gaps', [])])

            company_safe = job.get('company', '').replace(' ', '_').replace('/', '_').replace('\\', '_')

            job_cards_html += f"""
            <div class="job-card {category}" data-category="{category}">
                <div class="job-header">
                    <h2>{job.get('job_title', 'Unknown Title')}</h2>
                    <span class="fit-score">{job.get('fit_score', 0)}%</span>
                </div>
                <div class="job-meta">
                    <span class="company">{job.get('company', 'Unknown')}</span>
                    <span class="location">{job.get('location', 'Unknown')}</span>
                    <span class="source">{job.get('source', 'Unknown')}</span>
                </div>
                {cap_exempt_badge}
                <div class="tech-match">Tech Stack Match: {job.get('tech_stack_match', 'N/A')}%</div>
                <div class="experience-match">Experience: {job.get('experience_match', 'N/A')}</div>

                <div class="strengths">
                    <h4>&#10003; Strengths:</h4>
                    <ul>{strengths_html}</ul>
                </div>

                <div class="gaps">
                    <h4>&#9888; Gaps to Address:</h4>
                    <ul>{gaps_html}</ul>
                </div>

                <div class="reasoning">
                    <p><strong>Reasoning:</strong> {job.get('reasoning', 'No reasoning provided')}</p>
                </div>

                <div class="actions">
                    <a href="{job.get('job_url', '#')}"
                       class="apply-link"
                       target="_blank"
                       onclick="markAsClicked(this, 'job_{i}')">
                       View Job &amp; Apply
                    </a>
                    <a href="applications/{company_safe}_resume.docx" class="doc-link">Resume</a>
                    <a href="applications/{company_safe}_cover_letter.txt" class="doc-link">Cover Letter</a>
                </div>
            </div>
            """

        # Complete HTML
        html = f"""<!DOCTYPE html>
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
        <h1>&#127919; Job Applications Tracker</h1>
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
            clicked.forEach(function(jobId) {{
                let link = document.querySelector('[onclick*="' + jobId + '"]');
                if (link) link.classList.add('visited');
            }});
            updateStats();
        }};

        // Filter functionality
        function filterBy(category) {{
            let cards = document.querySelectorAll('.job-card');
            cards.forEach(function(card) {{
                if (category === 'all') {{
                    card.style.display = 'block';
                }} else if (category === 'not-applied') {{
                    let link = card.querySelector('.apply-link');
                    card.style.display = (link && link.classList.contains('visited')) ? 'none' : 'block';
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
</html>"""

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

        if cap_exempt is True:
            return '<div class="cap-exempt-badge">&#10003; Cap-Exempt Verified</div>'
        elif cap_exempt is False:
            return '<div class="cap-exempt-badge no">&#10007; NOT Cap-Exempt</div>'
        else:
            return '<div class="cap-exempt-badge unknown">&#9888; Cap-Exempt Status Unknown</div>'
