# Release Note Generator - Backend

This is the FastAPI backend that processes payloads from the GitHub Action, generates AI-powered release notes (via OpenRouter or similar), and serves them to the web dashboard.

## Requirements
- Python 3.8+
- SQLite (for local development) or PostgreSQL

## Local Setup

1. **Create and activate a virtual environment:**
   ```bash
   python -m venv venv
   # On Windows:
   venv\Scripts\activate
   # On macOS/Linux:
   source venv/bin/activate
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set environment variables:**
   Create a `.env` file or export the variables directly.
   ```bash
   # Required for AI generation
   export OPENROUTER_API_KEY="your-api-key"
   
   # Optional: Database URL (Defaults to local SQLite if omitted)
   # export DATABASE_URL="postgresql://user:password@localhost/dbname"
   ```

4. **Run the server:**
   ```bash
   uvicorn main:app --reload
   ```
   The backend will start at `http://localhost:8000`. 
   You can view the interactive API documentation at `http://localhost:8000/docs`.

## Key Endpoints
- `POST /draft-release`: Receives commit payloads and generates a draft release note.
- `GET /drafts`: Retrieves all pending drafts.
- `DELETE /drafts/{draft_id}`: Deletes a specific draft.
