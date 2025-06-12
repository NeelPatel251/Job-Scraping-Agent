import os
from urllib.parse import quote_plus
from dotenv import load_dotenv

load_dotenv()

TARGET_URL = "https://www.linkedin.com"
GEMINI_API_KEY = os.getenv("GOOGLE_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
LINKEDIN_EMAIL = os.getenv("LINKEDIN_EMAIL")
LINKEDIN_PASSWORD = os.getenv("LINKEDIN_PASS")
JOB_TITLE = "Data Scientist"
JOB_LOCATION = "Bangalore, India"

PHONE_NUMNER = "7046281329"
RESUME_PATH = "/home/neel/Desktop/HyperLink/Automatic_Job_Selection/Linked_IN/Agents/resume college 1.pdf"

def format_linkedin_job_url(base_url, job_title, location, easy_apply=True):
    """
    Format LinkedIn job search URL with proper URL encoding
    
    Args:
        base_url (str): Base LinkedIn URL
        job_title (str): Job title to search for
        location (str): Location to search in
        easy_apply (bool): Whether to filter for Easy Apply jobs
    
    Returns:
        str: Formatted LinkedIn job search URL
    """
    
    encoded_keywords = quote_plus(job_title)
    encoded_location = quote_plus(location)
    
    job_search_url = f"{base_url}/jobs/search"
    
    params = []
    if easy_apply:
        params.append("f_AL=true")  # Easy Apply filter
    params.append(f"keywords={encoded_keywords}")
    params.append(f"location={encoded_location}")

    query_string = "&".join(params)
    
    return f"{job_search_url}?{query_string}"

# Usage example
TARGET_JOB_URL = format_linkedin_job_url(TARGET_URL, JOB_TITLE, JOB_LOCATION)