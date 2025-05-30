import os
from dotenv import load_dotenv

load_dotenv()

TARGET_URL = "https://www.linkedin.com"
GEMINI_API_KEY = os.getenv("GOOGLE_API_KEY")
LINKEDIN_EMAIL = os.getenv("LINKEDIN_EMAIL")
LINKEDIN_PASSWORD = os.getenv("LINKEDIN_PASS")
JOB_TITLE = "Software Developer" 
JOB_LOCATION = "New York"