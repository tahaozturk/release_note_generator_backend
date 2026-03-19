from typing import List, Optional
from pydantic import BaseModel
from sqlalchemy import Column, Integer, String, Text
from sqlalchemy.orm import declarative_base

Base = declarative_base()

class GitHubInstallation(Base):
    __tablename__ = "github_installations"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, index=True) # Extracted from Supabase JWT sub
    installation_id = Column(Integer, unique=True, index=True)

class RepositorySetting(Base):
    __tablename__ = "repository_settings"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, index=True)
    repository = Column(String, index=True) # e.g. "owner/repo"
    tracking_method = Column(String, default="push") # "push" or "tag"

# SQLAlchemy Database Model
class ReleaseDraft(Base):
    __tablename__ = "release_drafts"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, index=True, nullable=True)
    repository = Column(String, index=True)
    base_ref = Column(String)
    head_ref = Column(String)
    
    technical_note = Column(Text)
    marketing_note = Column(Text)
    hype_note = Column(Text)
    
    # Caching reformatted versions
    cached_appstore_note = Column(Text, nullable=True)
    cached_appstore_source = Column(Text, nullable=True) # The exact markdown that generated this cached note
    cached_googleplay_note = Column(Text, nullable=True)
    cached_googleplay_source = Column(Text, nullable=True)
    
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
    draft_id: int
    content: str
    platform: str # "markdown", "appstore", "googleplay"

class TranslateRequest(BaseModel):
    content: str
    target_languages: List[str]

class RepoSettings(BaseModel):
    repository: str
    tracking_method: str # "push" or "tag"
