import os
from typing import List, Optional

import jwt as pyjwt
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from supabase import Client, create_client

try:
    import github_app as gh_app
except ImportError:
    gh_app = None
import json

# Database setup
DATABASE_URL = os.environ.get("DATABASE_URL")
if DATABASE_URL:
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
    engine = create_engine(DATABASE_URL)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(BASE_DIR, "release_notes_final.db").replace("\\", "/")
    SQLALCHEMY_DATABASE_URL = f"sqlite:///{db_path}"
    engine = create_engine(
        SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

from ai import get_generated_notes, reformat_content, translate_content
from models import (
    Base,
    CommitInput,
    FileInput,
    GitHubInstallation,
    ReformatRequest,
    ReleaseDraft,
    ReleasePayload,
    TranslateRequest,
    RepositorySetting,
    RepoSettings,
)

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Release Note Architect API")

security = HTTPBearer()


def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    try:
        # Extract the Supabase URL dynamically from the token issuer
        unverified_payload = pyjwt.decode(token, options={"verify_signature": False})
        iss = unverified_payload.get("iss")
        if not iss:
            raise HTTPException(status_code=401, detail="Invalid token: missing issuer")

        supabase_url = iss.replace("/auth/v1", "")
        anon_key = os.environ.get("SUPABASE_ANON_KEY")

        if not anon_key:
            raise HTTPException(
                status_code=500,
                detail="SUPABASE_ANON_KEY environment variable is required",
            )

        # Use the official Supabase SDK, which securely handles all algorithms (ES256, HS256) via the /auth/v1/user endpoint
        supabase: Client = create_client(supabase_url, anon_key)
        user_resp = supabase.auth.get_user(token)

        if not user_resp or not user_resp.user:
            raise HTTPException(status_code=401, detail="Invalid or expired token")

        # We must return a dictionary payload mapping `sub` to the user ID to match the rest of the backend
        return {"sub": user_resp.user.id}
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}")


# Setup CORS for Frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "https://release-note-generator-frontend.vercel.app",
        "https://release-note-generator-frontend.vercel.app/",  # With slash just in case
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def run_migrations():
    """Run migrations once at startup."""
    from sqlalchemy import text

    db = SessionLocal()
    try:
        # These columns were added later in development.
        # We try to add them if they don't exist.
        columns = [
            "cached_appstore_note",
            "cached_appstore_source",
            "cached_googleplay_note",
            "cached_googleplay_source",
            "user_id",
        ]
        for col in columns:
            try:
                db.execute(text(f"ALTER TABLE release_drafts ADD COLUMN {col} TEXT"))
                db.commit()
            except Exception:
                db.rollback()  # Crucial for Postgres: rollback the failed statement

    finally:
        db.close()


# Run migrations once when the module loads
Base.metadata.create_all(bind=engine)
run_migrations()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.get("/")
async def root():
    return {"message": "Release Note Architect Backend is Running", "docs": "/docs"}


@app.get("/health")
async def health():
    return {"status": "healthy"}


@app.post("/draft-release")
async def create_draft_release(payload: ReleasePayload):
    # Failsafe: Ensure tables exist
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        return await process_release_payload(payload, db, user_id=None)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


async def process_release_payload(
    payload: ReleasePayload, db: Session, user_id: str = None
):
    """Internal helper to process a release payload and generate AI notes."""
    commits_text = "\n".join([f"- {c.message} ({c.author})" for c in payload.commits])
    diffs_text = ""
    for f in payload.files:
        diff_text = f.patch if f.patch else ""
        diffs_text += (
            f"\nFile: {f.filename} (+{f.additions}/-{f.deletions})\n{diff_text}\n---"
        )

    try:
        notes = await get_generated_notes(commits_text, diffs_text)
    except Exception as e:
        # Fallback notes
        notes = {
            "technical": f"AI generation failed: {str(e)}",
            "marketing": "AI generation is temporarily unavailable.",
            "hype": "AI is taking a break! ☕",
        }

    db_draft = ReleaseDraft(
        repository=payload.repository,
        base_ref=payload.base_ref,
        head_ref=payload.head_ref,
        technical_note=notes.get("technical", "N/A"),
        marketing_note=notes.get("marketing", "N/A"),
        hype_note=notes.get("hype", "N/A"),
        status="pending",
        user_id=user_id,
    )

    db.add(db_draft)
    db.commit()
    db.refresh(db_draft)
    return {"message": "Draft created successfully", "id": db_draft.id}


@app.post("/webhook")
async def github_webhook(
    request: Request,
    x_github_event: str = Header(None),
    x_hub_signature_256: str = Header(None),
):
    body = await request.body()

    # Check if dependencies are loaded
    if gh_app is None:
        return {
            "status": "error",
            "reason": "GitHub App dependencies (PyJWT/cryptography) are not installed on the server.",
        }

    # 1. Verify Signature (Graceful fallback if secret is missing)
    if not gh_app.verify_signature(body, x_hub_signature_256):
        # We only strictly enforce if the secret is configured
        if os.environ.get("GITHUB_WEBHOOK_SECRET"):
            raise HTTPException(status_code=401, detail="Invalid signature")

    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    # 2. Handle Installation
    if x_github_event == "installation":
        action = payload.get("action")
        install_id = payload.get("installation", {}).get("id")
        repos = [r.get("full_name") for r in payload.get("repositories", [])]
        print(f"App {action} on installation {install_id} for Repos: {repos}")
        return {"status": "accepted"}

    # 3. Handle Push
    if x_github_event == "push":
        # Check if App config is present before attempting to use it
        if not os.environ.get("GITHUB_APP_ID") or not os.environ.get(
            "GITHUB_PRIVATE_KEY"
        ):
            return {
                "status": "error",
                "reason": "GitHub App configuration missing on server. Webhook cannot be processed.",
            }

        ref = payload.get("ref", "")
        repo_data = payload.get("repository", {})
        default_branch = repo_data.get("default_branch", "main")

        if ref != f"refs/heads/{default_branch}":
            return {"status": "ignored", "reason": "Not a push to default branch"}

        owner = repo_data.get("owner", {}).get("login")
        repo_name = repo_data.get("name")
        installation_id = payload.get("installation", {}).get("id")

        if not installation_id:
            return {"status": "error", "reason": "No installation ID found"}

        db = SessionLocal()
        try:
            full_repo_name = f"{owner}/{repo_name}"
            # Find the mapped user_id
            installation = (
                db.query(GitHubInstallation)
                .filter(GitHubInstallation.installation_id == installation_id)
                .first()
            )
            user_id = installation.user_id if installation else None
            
            # Find tracking settings
            settings = (
                db.query(RepositorySetting)
                .filter(RepositorySetting.repository == full_repo_name)
                .first()
            )
            tracking_method = settings.tracking_method if settings else "push"

            base = payload.get("before")
            head = payload.get("after")

            if tracking_method == "tag":
                if not ref.startswith("refs/tags/"):
                    return {"status": "ignored", "reason": "Repo is in 'tag' mode. Push ignored."}
                
                new_tag = ref.replace("refs/tags/", "")
                print(f"Processing TAG push: {new_tag} for {full_repo_name}")
                
                # For tags, we need to determine the base (previous tag)
                all_tags = await gh_app.list_repo_tags(owner, repo_name, installation_id)
                if len(all_tags) < 2:
                    # Initial tag or only one tag - fallback to parent or first commit
                    base = f"{head}^"
                else:
                    # GitHub API returns tags in reverse chronological order
                    if all_tags[0]["name"] == new_tag:
                        base = all_tags[1]["name"]
                    else:
                        base = all_tags[0]["name"]
                
                # When comparing by tag names, head is just the tag name itself
                head = new_tag
            else:
                # Standard push mode
                if ref.startswith("refs/tags/"):
                    return {"status": "ignored", "reason": "Repo is in 'push' mode. Tag ignored."}
                
                if ref != f"refs/heads/{default_branch}":
                    return {"status": "ignored", "reason": f"Not default branch ({default_branch})"}

            print(f"Processing comparison for {full_repo_name}: {base} -> {head}")

            # Fresh branch/Initial push handling for commits
            if base == "0000000000000000000000000000000000000000" and not tracking_method == "tag":
                base = f"{head}^"

            # Fetch compare data from GitHub
            compare_data = await gh_app.get_repo_compare(
                owner, repo_name, base, head, installation_id
            )

            # Transform and save
            internal_payload_dict = gh_app.parse_compare_payload(compare_data)
            internal_payload_dict["repository"] = full_repo_name
            internal_payload_dict["base_ref"] = base[:7] if len(base) > 7 else base
            internal_payload_dict["head_ref"] = head[:7] if len(head) > 7 else head

            internal_payload = ReleasePayload(**internal_payload_dict)
            await process_release_payload(internal_payload, db, user_id)
            return {"status": "success", "triggered": True}
        except Exception as e:
            print(f"Error processing webhook: {e}")
            return {"status": "error", "reason": str(e)}
        finally:
            db.close()

    return {"status": "ignored", "event": x_github_event}


@app.get("/settings/{owner}/{repo}")
def get_repository_settings(
    owner: str, repo: str, db: Session = Depends(get_db), token: dict = Depends(verify_token)
):
    user_id = token.get("sub")
    full_name = f"{owner}/{repo}"
    settings = (
        db.query(RepositorySetting)
        .filter(RepositorySetting.user_id == user_id, RepositorySetting.repository == full_name)
        .first()
    )
    if not settings:
        return {"repository": full_name, "tracking_method": "push"}
    return {"repository": full_name, "tracking_method": settings.tracking_method}


@app.post("/settings")
def update_repository_settings(
    req: RepoSettings, db: Session = Depends(get_db), token: dict = Depends(verify_token)
):
    user_id = token.get("sub")
    settings = (
        db.query(RepositorySetting)
        .filter(RepositorySetting.user_id == user_id, RepositorySetting.repository == req.repository)
        .first()
    )
    if settings:
        settings.tracking_method = req.tracking_method
    else:
        settings = RepositorySetting(
            user_id=user_id, repository=req.repository, tracking_method=req.tracking_method
        )
        db.add(settings)
    db.commit()
    return {"message": "Settings updated"}


@app.get("/drafts")
def get_drafts(db: Session = Depends(get_db), token: dict = Depends(verify_token)):
    user_id = token.get("sub")
    if user_id:
        drafts = db.query(ReleaseDraft).filter(ReleaseDraft.user_id == user_id).all()
    else:
        drafts = []
    return drafts


class InstallationInput(BaseModel):
    installation_id: int


@app.post("/installations")
def register_installation(
    req: InstallationInput,
    db: Session = Depends(get_db),
    token: dict = Depends(verify_token),
):
    user_id = token.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="User ID missing from token")

    existing = (
        db.query(GitHubInstallation)
        .filter(GitHubInstallation.installation_id == req.installation_id)
        .first()
    )
    if existing:
        if existing.user_id != user_id:
            existing.user_id = user_id
            db.commit()
    else:
        new_inst = GitHubInstallation(
            user_id=user_id, installation_id=req.installation_id
        )
        db.add(new_inst)
        db.commit()
    return {"message": "Installation registered"}


@app.delete("/drafts/{draft_id}")
def delete_draft(
    draft_id: int, db: Session = Depends(get_db), token: dict = Depends(verify_token)
):
    draft = db.query(ReleaseDraft).filter(ReleaseDraft.id == draft_id).first()
    if draft:
        db.delete(draft)
        db.commit()
        return {"message": "Deleted"}
    raise HTTPException(status_code=404, detail="Draft not found")


@app.post("/reformat")
async def api_reformat_content(
    req: ReformatRequest,
    db: Session = Depends(get_db),
    token: dict = Depends(verify_token),
):
    try:
        draft = db.query(ReleaseDraft).filter(ReleaseDraft.id == req.draft_id).first()
        if not draft:
            raise HTTPException(status_code=404, detail="Draft not found")

        # Check Cache (Ensure the generated output matches the *exact* input source)
        if (
            req.platform == "appstore"
            and draft.cached_appstore_note
            and draft.cached_appstore_source == req.content
        ):
            return {"content": draft.cached_appstore_note}
        if (
            req.platform == "googleplay"
            and draft.cached_googleplay_note
            and draft.cached_googleplay_source == req.content
        ):
            return {"content": draft.cached_googleplay_note}
        if req.platform == "markdown":
            return {"content": req.content}

        # Call AI if not cached or source changed
        reformatted = await reformat_content(req.content, req.platform)

        # Save to Cache and track source
        if req.platform == "appstore":
            draft.cached_appstore_note = reformatted
            draft.cached_appstore_source = req.content
        elif req.platform == "googleplay":
            draft.cached_googleplay_note = reformatted
            draft.cached_googleplay_source = req.content

        db.commit()
        return {"content": reformatted}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/translate")
async def api_translate_content(
    req: TranslateRequest, token: dict = Depends(verify_token)
):
    try:
        translations = await translate_content(req.content, req.target_languages)
        return translations
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
