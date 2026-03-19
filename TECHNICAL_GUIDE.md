# Technical Guide: Release Note Architect (Backend)

This document provides a comprehensive technical overview of the "Release Note Architect" backend project. It is designed to help future developers (and AI assistants) understand the architecture, database schema, and core business logic.

## 1. Project Overview
**Release Note Architect Backend** is a FastAPI-powered service that handles GitHub webhooks, coordinates AI-driven release note generation, and manages persistent storage for release drafts.

### Tech Stack
- **Framework**: FastAPI (Python)
- **Database**: 
    - **Local**: SQLite (`release_notes_final.db`)
    - **Production**: PostgreSQL (configured via `DATABASE_URL`)
- **ORM**: SQLAlchemy
- **Authentication**: Supabase JWT (ES256 asymmetric verification)
- **AI Integration**: OpenRouter API (Accessing various LLMs)
- **GitHub Integration**: GitHub App (via `httpx` and `PyJWT`)
- **JSON Handling**: Pydantic models for request/response validation

---

## 2. Project Structure

```text
backend/
├── main.py                 # FastAPI app entry point (Routes & Middleware)
├── models.py               # SQLAlchemy Database Models & Pydantic Schemas
├── ai.py                   # AI logic (Prompts, API calls, Parsing)
├── github_app.py           # GitHub App authentication & Webhook processing
├── release_notes_final.db   # Local SQLite Database (Development)
├── requirements.txt        # Python dependencies
└── docs/                   # Documentation & Migration summaries
```

---

## 3. Core Technical Flows

### Authentication (ES256 JWT)
The backend implements a secure token verification system in `main.py`:
1. **Dynamic Issuer Verification**: Extracts the Supabase project URL from the `iss` claim in the JWT.
2. **SDK Integration**: Uses the official `supabase-py` SDK to call the `/auth/v1/user` endpoint. This ensures the token is valid, hasn't been revoked, and was issued by the trusted Supabase instance for the specific project.
3. **User Extraction**: Returns a standard `sub` payload (Supabase UUID) for downstream route dependency injection.

### AI Generation Pipeline (`ai.py`)
- **Raw Data Collection**: Aggregates commit messages and filtered file patches (diffs).
- **Multipart Prompts**: The system requests three distinct types of notes in a single LLM pass:
    - `technical`: Standard engineering-focused notes.
    - `marketing`: User-benefit focused notes.
    - `hype`: Viral/Social-style excitement notes.
- **Robust Parsing**: Includes fallback logic to extract JSON from AI responses if the model includes conversational filler.

### GitHub Webhook Processing
- **Push Event**: Triggered on push to the default branch.
- **Comparison Engine**: 
    - Requests `compare` data from GitHub API using a GitHub App installation token.
    - Parses commits and file changes (additions, deletions, patches).
- **Draft Synchronization**: If the repository is connected to an installation linked to a user, the generated draft is automatically assigned to that user's view.

---

## 4. Database Schema (`models.py`)

### `release_drafts` table
- **id**: Primary key.
- **user_id**: Supabase UUID (links draft to a specific user).
- **repository**: Full name of the repo (e.g., `owner/repo`).
- **technical_note/marketing_note/hype_note**: AI-generated content.
- **Caching**: Contains `cached_*_note` and `cached_*_source` columns to prevent redundant AI calls when a user toggles between platforms (App Store, Google Play) without changing the base content.

### `github_installations` table
- **installation_id**: The ID assigned by GitHub when the app is installed.
- **user_id**: The Supabase UUID of the user who registered this installation.

### `repository_settings` table
- **repository**: Full name of the repo.
- **tracking_method**: "push" (every commit) or "tag" (only on version bumps).

---

## 5. API Endpoints Summary

- **`POST /webhook`**: Receives GitHub push/installation events. (Public)
- **`GET /drafts`**: Lists all drafts for the authenticated user. (Protected)
- **`POST /installations`**: Links a GitHub installation ID to the current user. (Protected)
- **`POST /reformat`**: High-performance reformatting of notes for specific App Stores with built-in caching. (Protected)
- **`POST /translate`**: AI-driven multi-language translation. (Protected)

---

## 6. Environment Variables
- `DATABASE_URL`: Connection string for PostgreSQL (if not set, SQLite is used).
- `SUPABASE_ANON_KEY`: Public key for Supabase Auth integration.
- `OPENROUTER_API_KEY`: Key for AI generation services.
- `GITHUB_APP_ID`: GitHub App unique identifier.
- `GITHUB_PRIVATE_KEY`: Private PEM key for the GitHub App.
- `GITHUB_WEBHOOK_SECRET`: Secret for verifying webhook signatures.
