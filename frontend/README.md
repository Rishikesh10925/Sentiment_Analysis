# Frontend — Social Media Sentiment & Trend Analysis Dashboard

React + TypeScript + Vite, styled with Tailwind CSS v4, charted with
Recharts, iconed with Lucide React. See the main project
[README.md](../README.md) (Stage 9 section) for full details on what
this dashboard shows and how it was verified.

## Run

```bash
npm install
npm run dev       # http://localhost:5173, proxies /api/* to the backend on :8000
```

The backend (`uvicorn backend.main:app --port 8000`, from the project
root) must be running for the dashboard to show real data.

## Structure

```
src/
├── api/          # typed fetch client + a loading/error/data hook
├── components/    # Sidebar, StatCard, SentimentBadge, AlertBanner, loading/error/empty states
├── pages/         # Overview, Platforms, Topics, ContentExplorer, Alerts, UploadPage
├── types.ts       # types matching the FastAPI response shapes
└── App.tsx        # routing + responsive layout (sidebar collapses to a drawer on mobile)
```

## Build

```bash
npm run build      # type-checks (tsc -b) then builds to dist/
```
