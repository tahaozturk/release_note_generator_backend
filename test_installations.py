import os

from jose import jwt

secret = "dummy-secret"
os.environ["SUPABASE_JWT_SECRET"] = secret
os.environ["DATABASE_URL"] = "sqlite:///./release_notes_final.db"

# generate token
token = jwt.encode(
    {"sub": "test-user-id-123", "role": "authenticated"}, secret, algorithm="HS256"
)
print(f"TOKEN={token}")

import asyncio

import httpx


async def test_api():
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "http://localhost:8888/installations",
            json={"installation_id": 99999},
            headers={"Authorization": f"Bearer {token}"},
        )
        print("API Response:", resp.status_code, resp.text)


# We will run the server in a separate thread first
import threading

import uvicorn

from main import app


def run_server():
    uvicorn.run(app, host="127.0.0.1", port=8888, log_level="error")


t = threading.Thread(target=run_server, daemon=True)
t.start()

import time

time.sleep(2)  # wait for server to start

asyncio.run(test_api())
