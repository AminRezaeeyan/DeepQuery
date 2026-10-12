# DeepQuery web client

React + TypeScript + Vite front end for the DeepQuery API.

## Run

The Django API must be running on `127.0.0.1:8000` (see the main README).

```bash
cd client
npm install
npm run dev          # http://localhost:5173
```

In development Vite proxies `/api` and `/auth` to Django, so no CORS setup is needed.

| Variable | Purpose |
|---|---|
| `VITE_API_TARGET` | Where the dev proxy sends API calls. Default `http://127.0.0.1:8000`. |
| `VITE_API_BASE` | API origin for a production build served from a different host. Empty means same origin. |
| `VITE_GOOGLE_CLIENT_ID` | Shows the Google sign-in button. Must match `GOOGLE_CLIENT_ID` on the server. |

## Scripts

- `npm run dev` — dev server with hot reload
- `npm run build` — type-check and build to `dist/`
- `npm run typecheck` — type-check only

## Layout

```
src/
  lib/            API client, auth and theme state, formatting helpers
  components/     shared pieces: logo, markdown renderer, toasts, theme switch
  pages/          sign-in, sign-up and plans pages
  features/chat/  the workspace: sidebar, thread, composer, sources panel
  styles/         design tokens (dark and light) and component styles
```
