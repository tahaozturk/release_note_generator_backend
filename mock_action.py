import httpx
import asyncio

async def main():
    payload = {
        "repository": "ai_release_notes/test-repo",
        "base_ref": "v1.0.0",
        "head_ref": "v1.1.0",
        "commits": [
            {
                "sha": "8371df1",
                "message": "feat: added new awesome feature",
                "author": "Alice",
                "url": "http://mock/1"
            },
            {
                "sha": "95f5108",
                "message": "fix: resolved a nasty bug",
                "author": "Bob",
                "url": "http://mock/2"
            }
        ],
        "files": [
            {
                "filename": "feat.txt",
                "status": "added",
                "additions": 1,
                "deletions": 0,
                "changes": 1,
                "patch": "+Feature"
            },
            {
                "filename": "fix.txt",
                "status": "added",
                "additions": 1,
                "deletions": 0,
                "changes": 1,
                "patch": "+Fix"
            }
        ]
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.post("http://localhost:8000/draft-release", json=payload, timeout=60.0)
        print("Status", response.status_code)
        print("Body:", response.json())

if __name__ == "__main__":
    asyncio.run(main())
