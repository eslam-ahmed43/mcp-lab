import os

from dotenv import load_dotenv
from google import genai

load_dotenv()
client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
for model in client.models.list():
    actions = getattr(model, "supported_actions", None) or []
    if not actions or "generateContent" in actions:
        print(model.name)
