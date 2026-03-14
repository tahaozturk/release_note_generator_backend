from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
import os

from models import Base, ReleaseDraft, ReleasePayload
from ai import get_generated_notes

app = FastAPI(title="Release Note Architect API")

# Setup CORS for Frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Since this is a local tool 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database setup
DATABASE_URL = os.environ.get("DATABASE_URL")

if DATABASE_URL:
    # Supabase/PostgreSQL uses postgresql://, but SQLAlchemy often requires postgresql+psycopg2://
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
    engine = create_engine(DATABASE_URL)
else:
    # Local SQLite fallback
    SQLALCHEMY_DATABASE_URL = "sqlite:///./drafts.db"
    engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.post("/draft-release")
async def create_draft_release(payload: ReleasePayload, db: Session = Depends(get_db)):
    # Convert payload into text for the LLM
    commits_text = "\n".join([f"- {c.message} ({c.author})" for c in payload.commits])
    
    # We just grab filename and changes to keep the prompt small, plus a snippet of diff
    diffs_text = ""
    for f in payload.files:
        diff_text = f.patch if f.patch else ""
        diffs_text += f"\nFile: {f.filename} (+{f.additions}/-{f.deletions})\n{diff_text}\n---"
        
    try:
        notes = await get_generated_notes(commits_text, diffs_text)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
        
    db_draft = ReleaseDraft(
        repository=payload.repository,
        base_ref=payload.base_ref,
        head_ref=payload.head_ref,
        technical_note=notes.get("technical", ""),
        marketing_note=notes.get("marketing", ""),
        hype_note=notes.get("hype", ""),
        status="pending"
    )
    
    db.add(db_draft)
    db.commit()
    db.refresh(db_draft)
    
    return {"message": "Draft created successfully", "id": db_draft.id}

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
