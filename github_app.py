import os
import time
import hmac
import hashlib
import jwt
import httpx
from typing import Optional, List, Dict
from pydantic import BaseModel

# Environment Variables (to be set in .env)
APP_ID = os.environ.get("GITHUB_APP_ID")
PRIVATE_KEY = os.environ.get("GITHUB_PRIVATE_KEY") # Path to .pem file or PEM content
WEBHOOK_SECRET = os.environ.get("GITHUB_WEBHOOK_SECRET")

def verify_signature(payload: bytes, signature: str) -> bool:
    """Verify that the webhook payload was sent by GitHub."""
    if not WEBHOOK_SECRET:
        return True # Skip if not configured (for local dev)
    
    if not signature:
        return False
        
    sha_name, signature_val = signature.split('=')
    if sha_name != 'sha256':
        return False
        
    mac = hmac.new(WEBHOOK_SECRET.encode(), msg=payload, digestmod=hashlib.sha256)
    return hmac.compare_digest(mac.hexdigest(), signature_val)

def get_jwt() -> str:
    """Generate a JWT to authenticate as the GitHub App."""
    if not APP_ID or not PRIVATE_KEY:
        raise Exception("GITHUB_APP_ID or GITHUB_PRIVATE_KEY not configured")
    
    # Check if PRIVATE_KEY is a file path or the content itself
    pem_content = PRIVATE_KEY
    if os.path.exists(PRIVATE_KEY):
        with open(PRIVATE_KEY, "r") as f:
            pem_content = f.read()

    now = int(time.time())
    payload = {
        "iat": now - 60,
        "exp": now + (10 * 60),
        "iss": APP_ID
    }
    return jwt.encode(payload, pem_content, algorithm="RS256")

async def get_installation_token(installation_id: int) -> str:
    """Get an installation-specific access token."""
    app_jwt = get_jwt()
    url = f"https://api.github.com/app/installations/{installation_id}/access_tokens"
    
    headers = {
        "Authorization": f"Bearer {app_jwt}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28"
    }
    
    async with httpx.AsyncClient() as client:
        resp = await client.post(url, headers=headers)
        resp.raise_for_status()
        return resp.json()["token"]

async def get_repo_compare(owner: str, repo: str, base: str, head: str, installation_id: int):
    """Fetch commit and diff data from GitHub using an installation token."""
    token = await get_installation_token(installation_id)
    url = f"https://api.github.com/repos/{owner}/{repo}/compare/{base}...{head}"
    
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28"
    }
    
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, headers=headers)
        resp.raise_for_status()
        return resp.json()

def parse_compare_payload(data: dict):
    """Transform GitHub comparison data into our internal payload format."""
    commits = []
    for c in data.get("commits", []):
        commits.append({
            "sha": c["sha"],
            "message": c["commit"]["message"],
            "author": c["commit"]["author"]["name"],
            "url": c["html_url"]
        })
        
    files = []
    for f in data.get("files", []):
        files.append({
            "filename": f["filename"],
            "status": f["status"],
            "additions": f["additions"],
            "deletions": f["deletions"],
            "changes": f["changes"],
            "patch": f.get("patch")
        })
        
    return {
        "repository": data.get("base_commit", {}).get("repository", {}).get("full_name", "unknown"),
        "base_ref": data.get("base_commit", {}).get("sha", "unknown"), # simplified
        "head_ref": data.get("head_commit", {}).get("sha", "unknown"),
        "commits": commits,
        "files": files
    }
