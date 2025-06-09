import os
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
RESUME_PATH = "/home/neel/Desktop/HyperLink/Automatic Job Selection/Linked IN/Agents/rendercv-engineeringresumes-theme.pdf"