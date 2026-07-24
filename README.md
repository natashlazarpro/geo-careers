# GeoCareers — GIS Jobs Berlin

An interactive web map for exploring companies in Berlin that hire GIS professionals. Filter by sector, role type, company size, language requirements, and tech stack — then click any marker to open a company card with a direct link to their careers page.

**Live demo:** `https://natashlazarpro.github.io/gis-jobs-berlin/`

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

## Costs

Everything is free tier:

- **GitHub Pages** — free for public repos
- **Cloudflare Workers** — 100,000 requests/day free
- **Mapbox** — 50,000 map loads/month free

---
