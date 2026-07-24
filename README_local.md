# GeoCareers — GIS Jobs Berlin

An interactive web map for exploring companies in Berlin that hire GIS professionals. Filter by sector, role type, company size, language requirements, and tech stack — then click any marker to open a company card with a direct link to their careers page.

**Live demo:** `https://YOUR_USERNAME.github.io/gis-jobs-berlin/`

---

## Features

- **Interactive Mapbox map** with color-coded markers by industry sector
- **Sidebar company list** that syncs with map selection
- **Multi-filter panel** — sector, GIS role type (core product / dedicated team / side tool), company size, working language, tech stack
- **Company detail cards** with description, tech tags, Kununu rating link, and careers page link
- **Bilingual UI** — toggle between English and German
- **Secure data serving** via Cloudflare Worker (company data never lives in the public repo)

---

## Tech Stack

| Layer | Tool |
|---|---|
| Map | [Mapbox GL JS v3](https://docs.mapbox.com/mapbox-gl-js/) |
| Frontend | Vanilla HTML/CSS/JS — no build step |
| Data API | [Cloudflare Workers](https://workers.cloudflare.com/) |
| Hosting | GitHub Pages |

---

## Quick Start

### 1. Get a Mapbox token

Sign up at [account.mapbox.com](https://account.mapbox.com) (free tier is plenty). Copy your default public token and replace the placeholder in `index.html`:

```js
const MAPBOX_TOKEN = 'pk.your_token_here';
```

### 2. Deploy to GitHub Pages

1. Create a public GitHub repo
2. Upload `index.html`
3. Go to **Settings → Pages → Source** → select `main` → Save

Your map will be live at `https://YOUR_USERNAME.github.io/gis-jobs-berlin/`.

### 3. Serve company data via Cloudflare Worker (recommended)

Keeps your company dataset out of the public repo.

1. Go to [dash.cloudflare.com](https://dash.cloudflare.com) → **Workers & Pages → Create Worker**
2. Paste the contents of `worker.js` and deploy
3. In `worker.js`, set your GitHub Pages URL as the allowed origin:
   ```js
   const ALLOWED_ORIGIN = "https://YOUR_USERNAME.github.io";
   ```
4. In `index.html`, update the data URL:
   ```js
   const DATA_URL = 'https://your-worker.your-subdomain.workers.dev/companies';
   ```

See [DEPLOY.md](DEPLOY.md) for the full walkthrough.

---

## Costs

Everything is free tier:

- **GitHub Pages** — free for public repos
- **Cloudflare Workers** — 100,000 requests/day free
- **Mapbox** — 50,000 map loads/month free

---

## Project Structure

```
gis-jobs-berlin/
├── index.html      # Full single-page app
├── worker.js       # Cloudflare Worker (data API)
└── DEPLOY.md       # Step-by-step deployment guide
```

---

## About

Built as a GIS portfolio project. The goal was a clean, filterable resource for GIS job seekers in Berlin — something between a job board and a company explorer, grounded in an actual map.
