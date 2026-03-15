import os
import json
import httpx
import re
from typing import List

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

def format_as_markdown(data) -> str:
    """
    Intelligently converts AI-generated structured data (dicts/lists) into clean Markdown.
    """
    if isinstance(data, str):
        return data
    
    if isinstance(data, list):
        if not data:
            return "No changes reported."
        return "\n".join([f"- {str(item)}" for item in data])
    
    if isinstance(data, dict):
        lines = []
        for key, value in data.items():
            # If the value is a list of changes
            if isinstance(value, list) and value:
                lines.append(f"### {key}")
                lines.append("\n".join([f"- {str(item)}" for item in value]))
                lines.append("")
            # If the value is a sub-dict
            elif isinstance(value, dict) and value:
                lines.append(f"### {key}")
                lines.append(format_as_markdown(value))
                lines.append("")
            # Otherwise just a string or other primitive
            else:
                lines.append(f"**{key}**: {str(value)}")
        
        return "\n".join(lines).strip()
    
    return str(data)

async def get_generated_notes(commits_text: str, diffs_text: str) -> dict:
    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    
    prompt = f"""
    You are an expert technical writer and developer advocate.
    I have a list of commits and file diffs for a new release.
    Please analyze them and categorize the changes.
    
    Write three separate versions of release notes:
    1. "technical": A standard, engineer-focused release note with sections for Features, Fixes, and Internal changes.
    2. "marketing": A user-friendly, benefit-focused release note suitable for an App Store update.
    3. "hype": A fun, exciting, emoji-filled note suitable for Twitter or Discord.
    
    Return the response strictly as a JSON object with keys: "technical", "marketing", "hype".
    The values for these keys should ideally be Markdown strings. 
    Do not output any markdown formatting around the JSON response block itself. Just raw JSON.
    
    Commits:
    {commits_text}
    
    Diffs (truncated if necessary):
    {diffs_text[:5000]}
    """
    
    if not api_key:
        print("DEBUG: API Key not found. Falling back to mocked notes.")
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
                "model": "openrouter/auto",
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
        final_notes = {}
        
        # 1. Try parsing the whole content as JSON first
        try:
            parsed = json.loads(content.strip())
            if isinstance(parsed, dict):
                final_notes = parsed
        except json.JSONDecodeError:
            pass

        # 2. If that fails, try extracting from a markdown block or finding the first { and last }
        if not final_notes:
            # Try finding the first { and last }
            match = re.search(r'(\{.*\})', content, re.DOTALL)
            if match:
                try:
                    cleaned = match.group(1).strip()
                    parsed = json.loads(cleaned)
                    if isinstance(parsed, dict):
                        final_notes = parsed
                except json.JSONDecodeError:
                    # Try cleaning common AI "oopsies" like trailing commas
                    try:
                        # Very naive trailing comma fix
                        cleaned_v2 = re.sub(r',\s*\}', '}', cleaned)
                        parsed = json.loads(cleaned_v2)
                        if isinstance(parsed, dict):
                            final_notes = parsed
                    except:
                        pass

        # 3. Final formatting: ensure all keys are Markdown strings
        # We look for our expected keys
        result = {
            "technical": "Draft not generated properly.",
            "marketing": "Update available.",
            "hype": "New version out! 🚀"
        }

        # If we successfully parsed a dict, use it
        if final_notes:
            for key in ["technical", "marketing", "hype"]:
                if key in final_notes:
                    result[key] = format_as_markdown(final_notes[key])
        else:
            # Absolute fallback: if we couldn't parse JSON, the AI likely just gave us a string
            # We put it in technical if it's long, otherwise use defaults
            if len(content) > 50:
                result["technical"] = content
            
        return result

async def reformat_content(content: str, platform: str) -> str:
    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    if not api_key:
        return f"[MOCK] Reformatted for {platform}: {content[:100]}..."

    platform_rules = {
        "appstore": "Focused on user experience, professional and welcoming. Use simple bullets or paragraphs. Max 4000 chars.",
        "googleplay": "Clear, concise, and functional. Max 500 characters for 'What's New' section.",
        "markdown": "Clean Markdown formatting with headers and bullet points."
    }
    
    prompt = f"""
    Reformat the following release notes specifically for the {platform.upper()} platform.
    
    Platform Guidelines:
    {platform_rules.get(platform, "Standard formatting.")}
    
    Notes to reformat:
    {content}
    
    Output ONLY the reformatted text. No coversational filler.
    """

    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": "openrouter/auto",
                "messages": [{"role": "user", "content": prompt}]
            },
            timeout=45.0
        )
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"].strip()

async def translate_content(content: str, target_languages: List[str]) -> dict:
    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    if not api_key:
        return {lang: f"[MOCK Translation ({lang})]: {content[:50]}..." for lang in target_languages}

    prompt = f"""
    Translate the following release notes into these languages: {", ".join(target_languages)}.
    
    Notes to translate:
    {content}
    
    Return the result strictly as a JSON object where the keys are the language names and values are the translated text.
    Do not output any markdown formatting around the JSON block. Just raw JSON.
    """

    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": "openrouter/auto",
                "messages": [{"role": "user", "content": prompt}]
            },
            timeout=90.0
        )
        response.raise_for_status()
        data = response.json()
        raw_result = data["choices"][0]["message"]["content"].strip()
        
        try:
            # Reuse logic for finding JSON block
            match = re.search(r'(\{.*\})', raw_result, re.DOTALL)
            if match:
                return json.loads(match.group(1).strip())
            return json.loads(raw_result)
        except:
            return {"error": "Failed to parse translations", "raw": raw_result}
