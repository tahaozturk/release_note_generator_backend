from typing import List, Optional
from pydantic import BaseModel
from sqlalchemy import Column, Integer, String, Text
from sqlalchemy.orm import declarative_base

Base = declarative_base()

# SQLAlchemy Database Model
class ReleaseDraft(Base):
    __tablename__ = "release_drafts"
    id = Column(Integer, primary_key=True, index=True)
    repository = Column(String, index=True)
    base_ref = Column(String)
    head_ref = Column(String)
    
    technical_note = Column(Text)
    marketing_note = Column(Text)
    hype_note = Column(Text)
    status = Column(String, default="pending")

# Pydantic Schemas for API Input
class CommitInput(BaseModel):
    sha: str
    message: str
    author: str
    url: str

class FileInput(BaseModel):
    filename: str
    status: str
    additions: int
    deletions: int
    changes: int
    patch: Optional[str] = None

class ReleasePayload(BaseModel):
    repository: str
    base_ref: str
    head_ref: str
    commits: List[CommitInput]
    files: List[FileInput]

class ReformatRequest(BaseModel):
    content: str
    platform: str # "markdown", "appstore", "googleplay"

class TranslateRequest(BaseModel):
    content: str
    target_languages: List[str]
