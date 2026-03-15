import os
import httpx
import json

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

async def get_generated_notes(commits_text: str, diffs_text: str) -> dict:
    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    
    prompt = f"""
    You are an expert technical writer and developer advocate.
    I have a list of commits and file diffs for a new release.
    Please analyze them and categorize the changes into "Features", "Fixes", and "Internal/Refactor".
    
    Then, write three separate versions of release notes:
    1. "technical": A standard, engineer-focused release note.
    2. "marketing": A user-friendly, benefit-focused release note suitable for an App Store update.
    3. "hype": A fun, exciting, emoji-filled note suitable for Twitter or Discord.
    
    Return the response strictly as a JSON object with keys: "technical", "marketing", "hype".
    Do not output any markdown formatting around the JSON block. Just raw JSON.
    
    Commits:
    {commits_text}
    
    Diffs (truncated if necessary):
    {diffs_text[:5000]}
    """
    
    if not api_key:
        print("DEBUG: API Key not found. Falling back to mocked notes.")
        # Fallback for testing if no key provided
        return {
            "technical": "## Features\n- Mocked feature\n## Fixes\n- Mocked fix",
            "marketing": "We fixed some bugs and added great new features!",
            "hype": "🚀 Yoooo! Huge update dropping! 🔥 Bugs squashed! 🐛🔨"
        }
        
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "HTTP-Referer": "http://localhost:8000",
                "Content-Type": "application/json"
            },
            json={
                "model": "openai/gpt-oss-120b:free", # Standard fast, smart model
                "messages": [
                    {"role": "user", "content": prompt}
                ]
            },
            timeout=30.0
        )
        
        response.raise_for_status()
        data = response.json()
        
        content = data["choices"][0]["message"]["content"]
        # Try to parse the json
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            # If it wrapped in markdown occasionally
            cleaned = content.replace("```json", "").replace("```", "").strip()
            return json.loads(cleaned)
