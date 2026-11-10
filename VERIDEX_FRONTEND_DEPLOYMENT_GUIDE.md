# VERIDEX — FRONTEND RENDER DEPLOYMENT GUIDE
**Author**: Amoolya (Frontend Integration Engineer)  
**Date**: November 2026  
**Target Environment**: Render Static Site  
**Service Type**: Static Site (Vite + React)  

---

## 1. Overview

This guide provides instructions for deploying the **VERIDEX** frontend on **Render** as a high-performance **Static Site**, configuring production API connectivity, managing environment variables securely, and coordinating CORS requirements with the backend service.

---

## 2. Render Static Site Configuration

In the Render Dashboard ([dashboard.render.com](https://dashboard.render.com/)):

1. Click **New +** → Select **Static Site**.
2. Connect the Git repository: `https://github.com/janyagowda006/VERIDEX-AI`.
3. Set the deployment parameters:

| Configuration Field | Recommended Production Value |
| :--- | :--- |
| **Name** | `veridex-ai-frontend` |
| **Branch** | `main` (or `team/frontend` during integration review) |
| **Root Directory** | `frontend` |
| **Build Command** | `npm run build` |
| **Publish Directory** | `dist` |
| **Auto-Deploy** | `Yes` (deploys on push to target branch) |

---

## 3. Environment Variable Configuration

Under the **Environment** tab in your Render Static Site settings:

| Key | Example Value | Description |
| :--- | :--- | :--- |
| `VITE_API_BASE_URL` | `https://veridex-backend.onrender.com` | Full HTTPS URL of the deployed FastAPI backend service (without trailing slash). |

> [!CAUTION]
> **Zero Secrets in Frontend Bundles**: Never place database passwords, JWT signing keys (`SECRET_KEY`), or LLM API keys (`GEMINI_API_KEY`) in frontend environment variables. Any variable prefixed with `VITE_` is compiled directly into client-side JavaScript and is visible to anyone inspecting browser network bundles.

---

## 4. Single Page Application (SPA) Rewrite Rule

Because VERIDEX is a Single Page Application (SPA) driven by client-side routing and internal state, any direct browser reloads or subpath visits must serve `index.html`.

In the Render Static Site dashboard:
1. Navigate to **Redirects / Rewrites**.
2. Add the following rewrite rule:
   - **Type**: `Rewrite`
   - **Source**: `/*`
   - **Destination**: `/index.html`
   - **Action**: Save Changes.

---

## 5. Backend CORS Coordination (Action Required by Gagandeep)

In production on Render:
- Frontend runs on: `https://veridex-ai-frontend.onrender.com`
- Backend runs on: `https://veridex-backend.onrender.com`

Because these are distinct origins, the FastAPI backend must include `CORSMiddleware` in `backend/app/main.py`:

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://veridex-ai-frontend.onrender.com",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

Without this configuration, browser requests (e.g., `POST /api/auth/login`) will fail with CORS preflight errors.

---

## 6. Pre-Flight Verification Checklist

Before announcing deployment readiness:

- [x] Run `npm run test` locally — verify all 30 tests pass.
- [x] Run `npm run build` locally — verify zero bundle errors.
- [x] Run `npm run lint` locally — verify zero syntax or compilation errors.
- [ ] Confirm `VITE_API_BASE_URL` is set in Render Static Site environment variables.
- [ ] Confirm backend has deployed with `CORSMiddleware` registered.
- [ ] Open deployed frontend URL and sign in with `analyst@veridex.ai` / `password123`.
- [ ] Verify that `GET /api/auth/me` returns HTTP 200 with the active user profile.
- [ ] Run an investigation query (e.g., "What is our gross revenue by region?").
- [ ] Verify that evidence pills, claim badges, candidate ranking, and robustness tests populate from live backend responses.
- [ ] Download an audit report (`.json` or `.md`) and confirm content integrity.

