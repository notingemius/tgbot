# D:\telegram_reminder_bot\quick_gemini_check.py
from google import genai
from google.genai import types
from config import GEMINI_API_KEY, GEMINI_MODEL

def main():
    if not GEMINI_API_KEY:
        print("GEMINI_API_KEY not set")
        return

    client = genai.Client(api_key=GEMINI_API_KEY)
    resp = client.models.generate_content(
        model=GEMINI_MODEL or "gemini-2.5-flash",
        contents="Say only: ok",
        # ВАЖНО: без request_options
        config=types.GenerateContentConfig(
            thinking_config=types.ThinkingConfig(thinking_budget=0)
        ),
    )
    print("REPLY:", (getattr(resp, "text", "") or "").strip())

if __name__ == "__main__":
    main()
