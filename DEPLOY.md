# GIS Jobs Berlin — Deployment Guide

## What you have

| File | Purpose |
|---|---|
| `index.html` | The full web map (frontend) |
| `worker.js` | Cloudflare Worker — serves company data securely |
| `DEPLOY.md` | This file |

---

## Step 1 — Get a free Mapbox token

1. Go to https://account.mapbox.com and create a free account
2. On your dashboard, copy the **Default public token** (starts with `pk.`)
3. Open `index.html` and replace this line:
   ```js
   const MAPBOX_TOKEN = 'YOUR_MAPBOX_TOKEN_HERE';
   ```
   with your real token.

---

## Step 2 — Publish to GitHub Pages

1. Create a new **public** GitHub repository (e.g. `gis-jobs-berlin`)
2. Upload `index.html` to the repo root (you can drag-drop in the browser)
3. Go to **Settings → Pages → Source** → select `main` branch → Save
4. Your site will be live at:
   ```
   https://YOUR_USERNAME.github.io/gis-jobs-berlin/
   ```

---

## Step 3 — Protect your data with Cloudflare Worker (optional but recommended)

This keeps company data out of your public GitHub repo.

### 3a. Deploy the worker

1. Go to https://dash.cloudflare.com → **Workers & Pages → Create Worker**
2. Paste the entire contents of `worker.js`
3. Click **Save and Deploy**
4. Copy the worker URL — looks like:
   ```
   https://gis-jobs-berlin.YOUR_SUBDOMAIN.workers.dev
   ```

### 3b. Set your allowed origin

In `worker.js`, update this line with your GitHub Pages URL:
```js
const ALLOWED_ORIGIN = "https://YOUR_USERNAME.github.io";
```

Re-deploy the worker after saving.

### 3c. Switch index.html to use the worker

At the top of the `<script>` block in `index.html`, add:
```js
const DATA_URL = 'https://gis-jobs-berlin.YOUR_SUBDOMAIN.workers.dev/companies';
```

Then replace the hardcoded `COMPANIES` array with a fetch:
```js
map.on('load', async () => {
  const res = await fetch(DATA_URL);
  const companies = await res.json();
  companies.forEach(c => { markers[c.id] = createMarker(c); });
  buildList(companies);
});
```

---

## How the data protection works

```
Visitor's browser
      │
      ▼
  index.html (public GitHub repo — no company data)
      │  fetch('/companies')
      ▼
  Cloudflare Worker
      │  checks Origin header == your GitHub Pages domain
      │  if wrong origin → 403 Forbidden
      ▼
  Returns company JSON only to your domain
```

**What this stops:** web scrapers, competitors copy-pasting your data into their sites, bots.
**What this doesn't stop:** a determined person manually reading your site. For full protection, you'd need user accounts + auth tokens — overkill for a portfolio project.

---

## Updating company data

- **With worker:** edit `worker.js`, re-deploy. The frontend auto-updates.
- **Without worker:** edit the `COMPANIES` array in `index.html`, commit to GitHub.

---

## Costs

Everything used here is **free**:
- GitHub Pages — free for public repos
- Cloudflare Workers — free tier: 100,000 requests/day
- Mapbox — free tier: 50,000 map loads/month
