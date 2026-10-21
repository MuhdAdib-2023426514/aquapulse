"""AquaPulse - Gemini Model Connectivity Test Script

Run this script to test if your GEMINI_API_KEY is working:
    uv run python test_gemini.py
"""

import os
import sys
from pathlib import Path

# 1. Load environment variables from .env
try:
    from dotenv import load_dotenv

    env_path = Path(__file__).resolve().parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)
        print(f"Loaded .env from: {env_path}", flush=True)
    else:
        print("[WARN] .env file not found in current directory!", flush=True)
except ImportError:
    pass

api_key = os.environ.get("GEMINI_API_KEY", "").strip()

# 2. Check if API Key exists
if not api_key:
    print("\n[ERROR] GEMINI_API_KEY is missing!", flush=True)
    print("Please add your key to .env:\nGEMINI_API_KEY=your_key_here\n", flush=True)
    sys.exit(1)

masked_key = f"{api_key[:6]}...{api_key[-4:]}" if len(api_key) > 10 else "***"
print(f"[OK] Found GEMINI_API_KEY: {masked_key} (length: {len(api_key)})", flush=True)

# 3. Test Gemini API
try:
    from google import genai

    client = genai.Client(api_key=api_key)

    model_name = "gemini-3.8-flash"
    print(f"\nSending test prompt to '{model_name}'...", flush=True)

    response = client.models.generate_content(
        model=model_name,
        contents="Say 'AquaPulse Gemini connection test successful!' in one short sentence.",
    )

    print("\n" + "=" * 50, flush=True)
    print("SUCCESS! Gemini API is working properly.", flush=True)
    print("=" * 50, flush=True)
    print(f"Model Response: {response.text.strip()}\n", flush=True)

except Exception as err:
    err_str = str(err)
    print("\n" + "!" * 50, flush=True)
    print("FAILED TO CONNECT TO GEMINI", flush=True)
    print("!" * 50, flush=True)
    print(f"Error details:\n{err}\n", flush=True)

    if "API_KEY_SERVICE_BLOCKED" in err_str:
        print("-" * 50, flush=True)
        print("FIX FOR 'API_KEY_SERVICE_BLOCKED':", flush=True)
        print("Your Google Cloud project has restricted this API key from calling", flush=True)
        print("the Generative Language API (generativelanguage.googleapis.com).", flush=True)
        print("", flush=True)
        print("How to fix this in Google Cloud Console:", flush=True)
        print("1. Go to: https://console.cloud.google.com/apis/credentials", flush=True)
        print("2. Click on this API Key.", flush=True)
        print("3. Under 'API restrictions':", flush=True)
        print("   - Choose 'Don't restrict key' OR", flush=True)
        print("   - If using 'Restrict key', make sure 'Generative Language API' is checked.", flush=True)
        print("4. Also ensure 'Generative Language API' is enabled in your project:", flush=True)
        print("   https://console.cloud.google.com/apis/library/generativelanguage.googleapis.com", flush=True)
        print("-" * 50, flush=True)
    elif "403" in err_str or "PERMISSION_DENIED" in err_str:
        print("-" * 50, flush=True)
        print("Make sure your API key has billing or access enabled for the Generative Language API.", flush=True)
        print("-" * 50, flush=True)

    sys.exit(2)
