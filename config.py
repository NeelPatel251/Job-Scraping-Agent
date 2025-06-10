import os
from dotenv import load_dotenv

load_dotenv()

TARGET_URL = "https://www.linkedin.com"
TARGET_JOB_URL = "https://www.linkedin.com/jobs/search?f_AL=true&keywords=Data%20Scientist&location=India"
GEMINI_API_KEY = os.getenv("GOOGLE_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
LINKEDIN_EMAIL = os.getenv("LINKEDIN_EMAIL")
LINKEDIN_PASSWORD = os.getenv("LINKEDIN_PASS")
JOB_TITLE = "Data Scientist" 
JOB_LOCATION = "Bangalore, India"
PHONE_NUMNER = "7046281329"
RESUME_PATH = "/home/neel/Desktop/HyperLink/Automatic Job Selection/Linked IN/Agents/rendercv-engineeringresumes-theme.pdf"