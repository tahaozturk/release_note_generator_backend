import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional

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
    engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

from models import Base, ReleaseDraft, CommitInput, FileInput, ReleasePayload, ReformatRequest, TranslateRequest
from ai import get_generated_notes, reformat_content, translate_content
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Release Note Architect API")

# Setup CORS for Frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "https://release-note-generator-frontend.vercel.app",
        "https://release-note-generator-frontend.vercel.app/", # With slash just in case
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
            "cached_appstore_note", "cached_appstore_source",
            "cached_googleplay_note", "cached_googleplay_source"
        ]
        for col in columns:
            try:
                db.execute(text(f"ALTER TABLE release_drafts ADD COLUMN {col} TEXT"))
                db.commit()
            except Exception:
                db.rollback() # Crucial for Postgres: rollback the failed statement
        
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
        commits_text = "\n".join([f"- {c.message} ({c.author})" for c in payload.commits])
        diffs_text = ""
        for f in payload.files:
            diff_text = f.patch if f.patch else ""
            diffs_text += f"\nFile: {f.filename} (+{f.additions}/-{f.deletions})\n{diff_text}\n---"
            
        try:
            notes = await get_generated_notes(commits_text, diffs_text)
        except Exception as e:
            # Fallback notes
            notes = {
                "technical": f"AI generation failed: {str(e)}",
                "marketing": "AI generation is temporarily unavailable.",
                "hype": "AI is taking a break! ☕"
            }
            
        db_draft = ReleaseDraft(
            repository=payload.repository,
            base_ref=payload.base_ref,
            head_ref=payload.head_ref,
            technical_note=notes.get("technical", "N/A"),
            marketing_note=notes.get("marketing", "N/A"),
            hype_note=notes.get("hype", "N/A"),
            status="pending"
        )
        
        db.add(db_draft)
        db.commit()
        db.refresh(db_draft)
        return {"message": "Draft created successfully", "id": db_draft.id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()

@app.get("/drafts")
def get_drafts(db: Session = Depends(get_db)):
    drafts = db.query(ReleaseDraft).all()
    return drafts

@app.delete("/drafts/{draft_id}")
def delete_draft(draft_id: int, db: Session = Depends(get_db)):
    draft = db.query(ReleaseDraft).filter(ReleaseDraft.id == draft_id).first()
    if draft:
        db.delete(draft)
        db.commit()
        return {"message": "Deleted"}
    raise HTTPException(status_code=404, detail="Draft not found")

@app.post("/reformat")
async def api_reformat_content(req: ReformatRequest, db: Session = Depends(get_db)):
    try:
        draft = db.query(ReleaseDraft).filter(ReleaseDraft.id == req.draft_id).first()
        if not draft:
            raise HTTPException(status_code=404, detail="Draft not found")
        
        # Check Cache (Ensure the generated output matches the *exact* input source)
        if req.platform == "appstore" and draft.cached_appstore_note and draft.cached_appstore_source == req.content:
            return {"content": draft.cached_appstore_note}
        if req.platform == "googleplay" and draft.cached_googleplay_note and draft.cached_googleplay_source == req.content:
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
async def api_translate_content(req: TranslateRequest):
    try:
        translations = await translate_content(req.content, req.target_languages)
        return translations
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
