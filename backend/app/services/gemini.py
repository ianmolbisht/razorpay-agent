from groq import Groq

from app.core.config import GROQ_API_KEY


client = Groq(
    api_key=GROQ_API_KEY
)

MODEL_NAME = "openai/gpt-oss-120b"