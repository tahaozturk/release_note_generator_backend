import os
import httpx

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # Manual fallback if dotenv not installed
    if os.path.exists(".env"):
        with open(".env") as f:
            for line in f:
                if "=" in line:
                    k, v = line.strip().split("=", 1)
                    os.environ[k.strip()] = v.strip().strip('"').strip("'")

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
                "Content-Type": "application/json"
            },
            json={
                "model": "openrouter/auto", # Automatically picks a good model
                "messages": [
                    {"role": "user", "content": prompt}
                ]
            },
            timeout=60.0
        )
        
        if response.status_code != 200:
            print(f"DEBUG: OpenRouter error {response.status_code}: {response.text}")
        
        response.raise_for_status()
        data = response.json()
            
        if "choices" not in data or not data["choices"]:
             return {
                "technical": "Error: No response from AI model",
                "marketing": "AI model did not return any choices.",
                "hype": "Oops! AI is shy today! 🙈"
            }
            
        content = data["choices"][0]["message"]["content"]
        
        # Robust parsing for AI responses
        final_notes = {
            "technical": content,
            "marketing": "Update available.",
            "hype": "New version is out! 🚀"
        }
        
        try:
            # Try parsing the raw content first
            parsed = json.loads(content)
            if isinstance(parsed, dict):
                final_notes.update(parsed)
        except json.JSONDecodeError:
            try:
                # Try stripping markdown code blocks
                cleaned = content.replace("```json", "").replace("```", "").strip()
                parsed = json.loads(cleaned)
                if isinstance(parsed, dict):
                    final_notes.update(parsed)
            except Exception as e:
                pass
                
        # Final safety check: ensure all keys are there
        for key in ["technical", "marketing", "hype"]:
             if key not in final_notes:
                 final_notes[key] = content[:500] if key == "technical" else "Update available."
                 
        return final_notes
