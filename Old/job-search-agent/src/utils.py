"""Utility functions for the job search agent."""
import json
import logging
import os
from datetime import datetime

logger = logging.getLogger(__name__)


def load_json(filepath, default=None):
    """Load JSON from file, returning default if not found."""
    if default is None:
        default = []
    try:
        with open(filepath, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return default
    except json.JSONDecodeError as e:
        logger.error(f"Error decoding JSON from {filepath}: {e}")
        return default


def save_json(filepath, data, indent=2):
    """Save data as JSON to filepath."""
    try:
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=indent)
        return True
    except Exception as e:
        logger.error(f"Error saving JSON to {filepath}: {e}")
        return False


def setup_logging(log_dir, log_file="search_log.txt", error_file="errors.log"):
    """Configure logging to file and console."""
    os.makedirs(log_dir, exist_ok=True)

    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'

    # Root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(logging.Formatter(log_format))

    # File handler (all logs)
    file_handler = logging.FileHandler(os.path.join(log_dir, log_file))
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(logging.Formatter(log_format))

    # Error file handler
    error_handler = logging.FileHandler(os.path.join(log_dir, error_file))
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(logging.Formatter(log_format))

    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(error_handler)

    return root_logger


def sanitize_filename(name):
    """Sanitize a string for use as a filename."""
    return name.replace(' ', '_').replace('/', '_').replace('\\', '_').replace(':', '_').replace('*', '_')


def timestamp():
    """Return current timestamp string."""
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def contains_dealbreaker(text, dealbreaker_phrases):
    """Check if text contains any dealbreaker phrases."""
    text_lower = text.lower()
    for phrase in dealbreaker_phrases:
        if phrase.lower() in text_lower:
            return phrase
    return None


def check_cap_exempt_by_name(company_name, indicators):
    """Quick name-based cap-exempt check."""
    company_lower = company_name.lower()
    for indicator in indicators:
        if indicator in company_lower:
            return True, indicator
    return False, None
