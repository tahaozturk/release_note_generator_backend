# Release Note Generator - Backend

This is the FastAPI backend that processes payloads from the GitHub Action, generates AI-powered release notes (via OpenRouter or similar), and serves them to the web dashboard.

**Authentication:** Uses Supabase JWT (ES256) for secure user authentication. See [Environment Setup](./docs/ENVIRONMENT_SETUP.md) for deployment configuration.

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
   
   # Required for Supabase JWT authentication (ES256)
   export SUPABASE_ANON_KEY="your-supabase-anon-key"
   
   # Optional: Database URL (Defaults to local SQLite if omitted)
   # export DATABASE_URL="postgresql://user:password@localhost/dbname"
   
   # Optional: GitHub App integration (for webhooks)
   # export GITHUB_APP_ID="your-app-id"
   # export GITHUB_PRIVATE_KEY="path/to/private-key.pem"
   # export GITHUB_WEBHOOK_SECRET="your-webhook-secret"
   ```
   
   For full environment variable details, see [Environment Setup Guide](./docs/ENVIRONMENT_SETUP.md).

4. **Run the server:**
   ```bash
   uvicorn main:app --reload
   ```
   The backend will start at `http://localhost:8000`. 
   You can view the interactive API documentation at `http://localhost:8000/docs`.

## Key Endpoints

### Authentication
All authenticated endpoints require a Supabase JWT token in the `Authorization: Bearer <token>` header.

### Release Notes
- `POST /draft-release`: Receives commit payloads and generates a draft release note.
- `GET /drafts`: Retrieves all drafts for the authenticated user.
- `DELETE /drafts/{draft_id}`: Deletes a specific draft.

### GitHub Integration
- `POST /webhook`: Receives GitHub webhook events (installation, push).
- `POST /installations`: Registers a GitHub installation for a user.

### AI Tools
- `POST /reformat`: Reformats release notes for specific platforms (App Store, Google Play, Markdown).
- `POST /translate`: Translates release notes into multiple languages.

### Health & Info
- `GET /`: API welcome message.
- `GET /health`: Health check endpoint.
- `GET /docs`: Interactive API documentation (Swagger UI).
