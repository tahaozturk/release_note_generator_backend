# Supabase JWT Migration Summary

## Overview

This document summarizes the changes made to update from legacy Supabase JWT authentication to the modern ES256-based approach using the Supabase SDK.

## What Changed

### 1. Removed Legacy HS256 Fallback

**Before:** The code had a fallback to HS256 symmetric key verification using `SUPABASE_JWT_SECRET`.

**After:** The code now exclusively uses the Supabase SDK's `/auth/v1/user` endpoint which handles ES256 (asymmetric) JWT verification automatically.

### 2. Environment Variable Changes

**Removed:**
- `SUPABASE_JWT_SECRET` - No longer needed

**Required:**
- `SUPABASE_ANON_KEY` - Your Supabase project's anonymous/public key

**Optional (but recommended):**
- `SUPABASE_URL` - Your Supabase project URL (can be extracted from token issuer)

### 3. Code Changes in `main.py`

The `verify_token` function was updated to:

1. Extract the Supabase URL from the token's `iss` claim
2. Use the Supabase SDK to call `/auth/v1/user` endpoint
3. Return the user ID from the response

**Key change:**
```python
# Old (removed):
secret = os.environ.get("SUPABASE_JWT_SECRET")
payload = pyjwt.decode(token, secret, algorithms=["HS256"], ...)

# New (current):
supabase: Client = create_client(supabase_url, anon_key)
user_resp = supabase.auth.get_user(token)
return {"sub": user_resp.user.id}
```

## Render Deployment Checklist

### Environment Variables to Add

1. **`SUPABASE_ANON_KEY`** (Required)
   - Find in Supabase Dashboard → Settings → API → anon/public
   - This is now the only Supabase auth variable needed

2. **`OPENROUTER_API_KEY`** (Required for AI features)
   - Find in OpenRouter Dashboard → Keys

3. **`DATABASE_URL`** (Required for production)
   - PostgreSQL connection string from Render Database

4. **GitHub App Variables** (Required for webhook integration)
   - `GITHUB_APP_ID`
   - `GITHUB_PRIVATE_KEY`
   - `GITHUB_WEBHOOK_SECRET`

### Deployment Steps

1. **Update Render Environment Variables**
   - Go to your Render Dashboard
   - Select your Web Service
   - Navigate to Environment tab
   - Add `SUPABASE_ANON_KEY` (remove `SUPABASE_JWT_SECRET` if present)
   - Add any other required variables

2. **Redeploy**
   - Trigger a manual deploy or push a change
   - Monitor logs for startup errors

3. **Verify**
   - Visit `https://your-service.onrender.com/health`
   - Check that no JWT-related errors appear in logs

## Testing Locally

1. Create a `.env` file with:
   ```
   SUPABASE_ANON_KEY=your-anon-key-here
   OPENROUTER_API_KEY=your-openrouter-key
   ```

2. Run the server:
   ```bash
   uvicorn main:app --reload
   ```

3. Test the health endpoint:
   ```bash
   curl http://localhost:8000/health
   ```

## Troubleshooting

### Error: "SUPABASE_ANON_KEY environment variable is required"

**Cause:** The `SUPABASE_ANON_KEY` is not set in your environment.

**Fix:** Add the variable to Render or your `.env` file.

### Error: "Invalid token"

**Cause:** Token verification failed.

**Fix:**
1. Verify `SUPABASE_ANON_KEY` matches your Supabase project
2. Ensure frontend is sending token in `Authorization: Bearer <token>` header
3. Check token hasn't expired

### Error: GitHub webhook not working

**Cause:** Missing GitHub App configuration.

**Fix:** Ensure all three GitHub variables are set:
- `GITHUB_APP_ID`
- `GITHUB_PRIVATE_KEY`
- `GITHUB_WEBHOOK_SECRET`

## Benefits of This Update

1. **Security:** ES256 uses asymmetric encryption (public/private key pairs) instead of symmetric keys
2. **Reliability:** Uses official Supabase SDK instead of manual JWT decoding
3. **Maintainability:** No need to manage JWT secrets manually
4. **Compatibility:** Works with modern Supabase authentication flows

## Files Modified

- `main.py` - Updated `verify_token` function
- `test_installations.py` - Updated test documentation
- `README.md` - Added authentication documentation
- `docs/ENVIRONMENT_SETUP.md` - New deployment guide
- `docs/JWT_MIGRATION_SUMMARY.md` - This file

## Questions?

Refer to `docs/ENVIRONMENT_SETUP.md` for detailed environment variable setup instructions.