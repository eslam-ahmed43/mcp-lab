import os

from dotenv import load_dotenv
from google import genai

load_dotenv()
client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
skip = ("image", "tts", "live", "audio", "embedding", "native", "robotics")
names = []
for model in client.models.list():
    actions = getattr(model, "supported_actions", None) or ["generateContent"]
    if "flash" in model.name and "generateContent" in actions:
        if not any(word in model.name for word in skip):
            names.append(model.name)
for name in names[:8]:
    try:
        client.models.generate_content(model=name, contents="Reply with the word ok.")
        print("OK    ", name)
    except Exception as exc:
        text = str(exc).replace("\n", " ")
        print("QUOTA " if "429" in text else "ERROR ", name, text[:70])
