# Environment Variables Setup for Render Deployment

This document outlines all the environment variables you need to configure in your Render dashboard for the Release Note Generator Backend.

## Required Environment Variables

### Supabase Authentication (Updated for Modern JWT)

These are required for the new ES256 JWT authentication:

| Variable Name | Description | Where to Find |
|--------------|-------------|---------------|
| `SUPABASE_ANON_KEY` | Your Supabase project's anonymous/public key | Supabase Dashboard → Settings → API → anon/public |
| `SUPABASE_URL` | Your Supabase project URL (optional - can be extracted from token) | Supabase Dashboard → Settings → API → Project URL |

**Important:** The legacy `SUPABASE_JWT_SECRET` is no longer needed. The backend now uses the Supabase SDK which handles ES256 JWT verification automatically via the `/auth/v1/user` endpoint.

### GitHub App Integration

Required for webhook processing and GitHub API calls:

| Variable Name | Description | Where to Find |
|--------------|-------------|---------------|
| `GITHUB_APP_ID` | Your GitHub App's ID | GitHub App Settings → About |
| `GITHUB_PRIVATE_KEY` | Your GitHub App's private key (PEM format) | GitHub App Settings → Private Keys |
| `GITHUB_WEBHOOK_SECRET` | Your GitHub App's webhook secret token | GitHub App Settings → Webhook |

### AI Integration

Required for generating release notes:

| Variable Name | Description | Where to Find |
|--------------|-------------|---------------|
| `OPENROUTER_API_KEY` | Your OpenRouter API key | OpenRouter Dashboard → Keys |

### Database

Required for data persistence:

| Variable Name | Description | Where to Find |
|--------------|-------------|---------------|
| `DATABASE_URL` | PostgreSQL connection string | Render Database → Connection Details |

**Example format:** `postgresql://user:password@host:port/database_name`

## Render Setup Steps

1. **Go to your Render Dashboard**
2. **Select your Web Service**
3. **Navigate to Environment tab**
4. **Add each variable** from the table above

### Setting GitHub Private Key in Render

The `GITHUB_PRIVATE_KEY` contains newlines which can be tricky in environment variables:

1. Copy the entire PEM content (including `-----BEGIN RSA PRIVATE KEY-----` and `-----END RSA PRIVATE KEY-----`)
2. In Render, paste it as a single line with `\n` for newlines, OR
3. Use the multi-line format if Render supports it

**Example:**
```
-----BEGIN RSA PRIVATE KEY-----\nMIIEpAIBAAKCAQEA...\n-----END RSA PRIVATE KEY-----
```

## Verification

After deploying, verify your setup:

1. **Health Check:** Visit `https://your-service.onrender.com/health`
2. **API Docs:** Visit `https://your-service.onrender.com/docs`
3. **Check Logs:** In Render Dashboard → Logs → Look for any startup errors

## Troubleshooting

### "SUPABASE_ANON_KEY environment variable is required"
- Make sure `SUPABASE_ANON_KEY` is set in Render environment variables
- Double-check there are no extra spaces or quotes

### "Invalid token" errors from frontend
- Verify `SUPABASE_ANON_KEY` matches your Supabase project
- Ensure your frontend is sending the token in the `Authorization: Bearer <token>` header

### GitHub Webhook not working
- Verify `GITHUB_APP_ID`, `GITHUB_PRIVATE_KEY`, and `GITHUB_WEBHOOK_SECRET` are all set
- Check GitHub App webhook URL points to your Render service URL
- Ensure the webhook events are configured (installation, push)

## Legacy Variables to Remove

The following variables are no longer used and can be removed from your Render environment:

- `SUPABASE_JWT_SECRET` (replaced by `SUPABASE_ANON_KEY`)

## Security Notes

- Never commit `.env` files to version control
- Render environment variables are encrypted at rest
- Rotate your keys periodically
- Use different keys for development and production