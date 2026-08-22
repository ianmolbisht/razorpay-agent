import os
from dotenv import load_dotenv

load_dotenv()


APP_NAME = os.getenv("APP_NAME", "Razorpay AI Merchant Agent")
APP_VERSION = os.getenv("APP_VERSION", "0.1.0")
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
DATABASE_URL = os.getenv("DATABASE_URL")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")