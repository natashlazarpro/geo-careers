// Builds one static page per city and language for search engines:
//   public/de/<slug>/index.html   (German, e.g. /de/muenchen)
//   public/en/<slug>/index.html   (English, e.g. /en/munich)
// and rewrites public/sitemap.xml with the homepage and every indexable city page.
//
// Runs during every Cloudflare build (scripts/build_site.sh). The employer list is fetched
// from the data-schield Worker at build time and written only into public/, never into the repo.
// Pages show a short summary and up to TEASER_MAX employer names; descriptions, addresses
// and links stay on the map. If the data can't be loaded the build fails, so Cloudflare keeps
// the last good version online.
//
// Usage: node scripts/build_cities.mjs [--data local.json] [--out public]

import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const SITE = 'https://geocareers.app';
const DATA_URL = 'https://data-schield.natashlazar-pro.workers.dev';
const TEASER_MAX = 10;   // employer names shown per city page
const INDEX_MIN = 5;     // fewer employers than this: page is noindex and left out of the sitemap

const arg = (name, fallback) => { const i = process.argv.indexOf(name); return i > 0 ? process.argv[i + 1] : fallback; };
const OUT = path.resolve(ROOT, arg('--out', 'public'));
const today = new Date().toISOString().slice(0, 10);

// ── City list and sector names: read from index.html so there is one source ────────────
const indexHtml = fs.readFileSync(path.join(ROOT, 'index.html'), 'utf8');
const literal = name => {
  const m = indexHtml.match(new RegExp(`const ${name} = (\\[[\\s\\S]*?\\n\\]|\\{[\\s\\S]*?\\n\\});`));
  if (!m) throw new Error(`${name} not found in index.html`);
  return Function(`"use strict"; return (${m[1]});`)();
};
const CITIES = literal('CITIES');
const SECTOR_DE = literal('SECTOR_DE');

const slug = s => s.toLowerCase().replace(/ä/g, 'ae').replace(/ö/g, 'oe').replace(/ü/g, 'ue').replace(/ß/g, 'ss')
  .normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
const norm = s => String(s || '').toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '').trim();
const esc = v => String(v ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const cityOf = name => { const n = norm(name); return CITIES.find(c => c.keys.some(k => norm(k) === n || n.startsWith(norm(k)))); };
const baseName = s => String(s || '').replace(/\s*\([^)]*\)/g, '').trim();
const sectorParts = s => String(s || '').split('/').map(p => p.trim()).filter(Boolean);

for (const c of CITIES) { c.slugDe = slug(c.de); c.slugEn = slug(c.en); }
const pageUrl = (c, lang) => `${SITE}/${lang}/${lang === 'de' ? c.slugDe : c.slugEn}`;

// ── Data ─────────────────────────────────────────────────────────────────────────────
async function loadRows() {
  const local = arg('--data');
  if (local) return JSON.parse(fs.readFileSync(local, 'utf8'));
  // data-schield answers only requests that come from the website
  const res = await fetch(DATA_URL + '/', { headers: { Origin: SITE } });
  if (!res.ok) throw new Error(`data-schield answered HTTP ${res.status}`);
  const rows = await res.json();
  if (!Array.isArray(rows) || rows.length < 50) throw new Error(`unexpected employer data (${Array.isArray(rows) ? rows.length : typeof rows} rows)`);
  return rows;
}

function cityStats(rows, city) {
  const offices = rows.filter(r => r.c_name && cityOf(r.city) === city);
  // one entry per employer, even with several offices in the city
  const byName = new Map();
  for (const r of offices) {
    const key = norm(baseName(r.c_name));
    const prev = byName.get(key);
    const rating = parseFloat(r.kununu_rate) || 0;
    if (!prev || rating > prev.rating) byName.set(key, { name: baseName(r.c_name), sector: r.sector || '', rating });
  }
  const employers = [...byName.values()];
  const count = (list) => { const m = new Map(); list.forEach(x => m.set(x, (m.get(x) || 0) + 1)); return [...m].sort((a, b) => b[1] - a[1]).map(x => x[0]); };
  const sectors = count(employers.flatMap(e => sectorParts(e.sector)).filter(s => s !== 'Other'));
  const tools = count(offices.flatMap(r => String(r.g_stack || '').split(',').map(t => t.trim()).filter(Boolean)));
  const teaser = [...employers].sort((a, b) => b.rating - a.rating || a.name.localeCompare(b.name, 'de')).slice(0, TEASER_MAX);
  return { n: employers.length, sectors: sectors.slice(0, 3), tools: tools.slice(0, 5), teaser };
}

// ── Text ─────────────────────────────────────────────────────────────────────────────
const listJoin = (items, and) => items.length < 2 ? items.join('') : `${items.slice(0, -1).join(', ')} ${and} ${items[items.length - 1]}`;
const TXT = {
  de: {
    htmlLang: 'de', other: 'en', name: c => c.de,
    title: (c, s) => `GIS-Arbeitgeber in ${c.de} – ${s.n} Unternehmen | GeoCareers`,
    h1: c => `GIS-Arbeitgeber in <em>${esc(c.de)}</em>`,
    eyebrow: 'GIS & Geodaten',
    sector: s => SECTOR_DE[s] || s,
    intro: (c, s, sec) => `${s.n === 1 ? 'Ein Unternehmen' : `${s.n} Unternehmen`} in ${c.de} arbeiten mit GIS und Geodaten` +
      (sec.length ? `, vor allem in den Bereichen ${listJoin(sec, 'und')}.` : '.') +
      (s.tools.length ? ` Häufige Werkzeuge: ${s.tools.join(', ')}.` : '') +
      ' Auf der Karte findest du alle mit Beschreibung, Adresse und Link zur Karriereseite.',
    desc: (c, s, sec) => `${s.n} Arbeitgeber für GIS und Geodaten in ${c.de}` + (sec.length ? `, vor allem ${listJoin(sec, 'und')}` : '') +
      `. ${s.tools.length ? `Tools: ${s.tools.slice(0, 3).join(', ')}. ` : ''}Alle mit Karriereseite auf der Karte von GeoCareers.`,
    listTitle: (s) => s.n > s.teaser.length ? `${s.teaser.length} von ${s.n} Arbeitgebern` : 'Arbeitgeber',
    cta: s => `Alle ${s.n} auf der Karte ansehen`,
    more: n => `und ${n} weitere auf der Karte`,
    others: 'Weitere Städte', switchLabel: 'English', switchAria: 'This page in English',
    nav: [['Karte', '/#map'], ['Arbeitgeber', '/#employers'], ['Städte', '/#cities']],
    feedback: 'Feedback', support: 'Support GeoCareers', home: 'Startseite',
    employersN: n => `${n} Arbeitgeber`,
  },
  en: {
    htmlLang: 'en', other: 'de', name: c => c.en,
    title: (c, s) => `GIS employers in ${c.en} – ${s.n} companies | GeoCareers`,
    h1: c => `GIS employers in <em>${esc(c.en)}</em>`,
    eyebrow: 'GIS & geodata',
    sector: s => s,
    intro: (c, s, sec) => `${s.n === 1 ? 'One company' : `${s.n} companies`} in ${c.en} ${s.n === 1 ? 'works' : 'work'} with GIS and geodata` +
      (sec.length ? `, mostly in ${listJoin(sec, 'and')}.` : '.') +
      (s.tools.length ? ` Common tools: ${s.tools.join(', ')}.` : '') +
      ' The map shows all of them with a description, address and a link to their careers page.',
    desc: (c, s, sec) => `${s.n} GIS and geodata employers in ${c.en}` + (sec.length ? `, mostly ${listJoin(sec, 'and')}` : '') +
      `. ${s.tools.length ? `Tools: ${s.tools.slice(0, 3).join(', ')}. ` : ''}All with their careers page on the GeoCareers map.`,
    listTitle: (s) => s.n > s.teaser.length ? `${s.teaser.length} of ${s.n} employers` : 'Employers',
    cta: s => `See all ${s.n} on the map`,
    more: n => `and ${n} more on the map`,
    others: 'Other cities', switchLabel: 'Deutsch', switchAria: 'Diese Seite auf Deutsch',
    nav: [['Map', '/#map'], ['Employers', '/#employers'], ['Cities', '/#cities']],
    feedback: 'Feedback', support: 'Support GeoCareers', home: 'Home',
    employersN: n => `${n} ${n === 1 ? 'employer' : 'employers'}`,
  },
};

// ── Page ─────────────────────────────────────────────────────────────────────────────
const FEEDBACK = 'https://docs.google.com/forms/d/e/1FAIpQLScQqgBiL9dsYR1wd1e3cI4jZoqLTO1dZvytucIfulvQEOIaEw/viewform';
const SUPPORT = 'https://buymeacoffee.com/natashlazarpro';
const CSS = `
:root{--ground:#fff;--surface:#fff;--surface-2:#fafaf8;--grid:#f1f1ee;--line:#e6e6e2;--line-2:#f0f0ec;--text:#3c3c3b;--muted:#6b6b69;--accent:#db3069;--accent-ink:#b0204f;--serif:'Newsreader',Georgia,serif;--sans:'Geist',system-ui,-apple-system,'Segoe UI',sans-serif}
*,*::before,*::after{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{margin:0;background-color:var(--ground);background-image:linear-gradient(var(--grid) 1px,transparent 1px),linear-gradient(90deg,var(--grid) 1px,transparent 1px);background-size:40px 40px;color:var(--text);font:15px/1.5 var(--sans);-webkit-font-smoothing:antialiased}
a{color:var(--accent-ink)}a:hover{color:#8a1840}
:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
.wrap{max-width:1120px;margin:0 auto;padding-left:max(40px,env(safe-area-inset-left));padding-right:max(40px,env(safe-area-inset-right))}
header{display:flex;flex-wrap:wrap;gap:16px 28px;align-items:center;justify-content:space-between;padding-top:28px;padding-bottom:28px}
.logo{color:var(--text);text-decoration:none;font-family:var(--serif);font-size:24px}
.support{display:inline-flex;align-items:center;gap:6px;height:38px;padding:0 16px;border-radius:999px;background:#db3169;color:#fff;text-decoration:none;font-size:14px;font-weight:500;white-space:nowrap}
.support:hover{color:#fff;filter:brightness(.95)}
.head-l{display:flex;flex-wrap:wrap;gap:16px 28px;align-items:center}
nav{display:flex;flex-wrap:wrap;gap:12px 28px;align-items:center;font-size:13px;margin-left:auto}
nav a{color:var(--text);text-decoration:none}
nav .ghost{border:1px solid var(--text);padding:8px 14px}
.lang{display:inline-flex;align-items:center;height:34px;padding:0 14px;border:1px solid var(--line);border-radius:999px;background:var(--surface);color:var(--text);text-decoration:none;font-size:12px}
main{padding-top:48px;padding-bottom:64px;display:flex;flex-direction:column;gap:40px}
.eyebrow{margin:0 0 14px;font-size:12px;letter-spacing:.12em;text-transform:uppercase;color:var(--muted)}
h1{margin:0;font-family:var(--serif);font-weight:400;font-size:clamp(44px,7vw,64px);line-height:1;letter-spacing:-.02em;text-wrap:balance}
h1 em{color:var(--accent)}
.intro{margin:20px 0 0;max-width:640px;font-size:17px;line-height:1.6}
.cta{display:inline-flex;align-items:center;justify-content:center;height:48px;padding:0 24px;margin-top:28px;border-radius:999px;background:var(--accent);color:#fff;text-decoration:none;font-size:14px;font-weight:500}
.cta:hover{color:#fff;filter:brightness(.95)}
.box{background:var(--surface);border:1px solid var(--line)}
.box-head{display:flex;justify-content:space-between;gap:12px;padding:14px 20px;border-bottom:1px solid var(--line);font-size:11px;letter-spacing:.12em;text-transform:uppercase;color:var(--muted)}
.list{margin:0;padding:0;list-style:none}
.list li{display:flex;flex-wrap:wrap;justify-content:space-between;gap:4px 16px;padding:16px 20px;border-bottom:1px solid var(--line-2)}
.list li:last-child{border-bottom:0}
.e-name{font-family:var(--serif);font-size:19px;line-height:1.2}
.e-sector{font-size:12px;color:var(--muted)}
.list .more{color:var(--muted);font-size:13px}
.tags{display:flex;flex-wrap:wrap;gap:6px;margin-top:16px}
.tag{display:inline-flex;align-items:center;height:28px;padding:0 11px;border:1px solid var(--line);background:var(--surface-2);border-radius:999px;font-size:12px}
.cities{display:flex;flex-wrap:wrap;gap:8px}
.cities a{display:inline-flex;align-items:center;height:34px;padding:0 14px;border:1px solid var(--line);border-radius:999px;background:var(--surface);color:var(--text);text-decoration:none;font-size:13px}
.cities a:hover{border-color:#d9d9d4}
h2{margin:0 0 14px;font-size:11px;font-weight:400;letter-spacing:.12em;text-transform:uppercase;color:var(--muted)}
footer{display:flex;flex-wrap:wrap;justify-content:space-between;gap:12px;padding-top:32px;padding-bottom:40px;font-size:12px;color:var(--muted)}
footer a{color:var(--muted)}
.mark{font-family:var(--serif);font-size:16px;color:var(--text);text-decoration:none}
@media (max-width:640px){
 .wrap{padding-left:max(16px,env(safe-area-inset-left));padding-right:max(16px,env(safe-area-inset-right))}
 header{padding-top:18px;padding-bottom:18px}
 header{gap:12px 16px}
 .head-l{display:contents}
 .logo{order:1}
 .lang{order:2;margin-left:auto}
 .support{order:3}
 nav{order:4;width:100%;margin-left:0;gap:10px 20px}
 .support{height:34px;font-size:13px}
 main{padding-top:24px;gap:32px}
 .intro{font-size:16px}
 .cta{width:100%}
}`;

function page(c, lang, s, ready) {
  const L = TXT[lang], O = TXT[L.other];
  const sec = s.sectors.map(L.sector);
  const url = pageUrl(c, lang), other = pageUrl(c, L.other);
  const mapUrl = `/?city=${c.slugDe}&lang=${lang}#map`;
  const title = L.title(c, s), desc = L.desc(c, s, sec);
  const indexable = s.n >= INDEX_MIN;
  const jsonLd = {
    '@context': 'https://schema.org', '@type': 'ItemList',
    name: title.replace(/ \| GeoCareers$/, ''), url, numberOfItems: s.teaser.length,
    itemListElement: s.teaser.map((e, i) => ({ '@type': 'ListItem', position: i + 1, item: { '@type': 'Organization', name: e.name, address: { '@type': 'PostalAddress', addressLocality: c.de, addressCountry: 'DE' } } })),
  };
  const others = CITIES.filter(x => x !== c && ready.has(x));
  return `<!DOCTYPE html>
<html lang="${L.htmlLang}">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover">
<title>${esc(title)}</title>
<meta name="description" content="${esc(desc)}">
${indexable ? '' : '<meta name="robots" content="noindex, follow">\n'}<link rel="canonical" href="${url}">
<link rel="alternate" hreflang="${lang}" href="${url}">
<link rel="alternate" hreflang="${L.other}" href="${other}">
<link rel="alternate" hreflang="x-default" href="${pageUrl(c, 'de')}">
<meta property="og:type" content="website">
<meta property="og:site_name" content="GeoCareers">
<meta property="og:locale" content="${lang === 'de' ? 'de_DE' : 'en_GB'}">
<meta property="og:url" content="${url}">
<meta property="og:title" content="${esc(title)}">
<meta property="og:description" content="${esc(desc)}">
<meta property="og:image" content="${SITE}/og-image.png?v=3">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta name="twitter:card" content="summary_large_image">
<link rel="icon" href="/favicon.svg" type="image/svg+xml">
<link rel="icon" href="/favicon-32.png" sizes="32x32" type="image/png">
<link rel="apple-touch-icon" href="/apple-touch-icon.png">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Newsreader:ital,opsz,wght@0,6..72,400;1,6..72,400&family=Geist:wght@400;500&display=swap" rel="stylesheet">
<style>${CSS}</style>
<script type="application/ld+json">${JSON.stringify(jsonLd).replace(/</g, '\\u003c')}</script>
<script>(function(c,l,a,r,i,t,y){c[a]=c[a]||function(){(c[a].q=c[a].q||[]).push(arguments)};t=l.createElement(r);t.async=1;t.src="https://www.clarity.ms/tag/"+i;y=l.getElementsByTagName(r)[0];y.parentNode.insertBefore(t,y);})(window,document,"clarity","script","zb35ete8b6");</script>
</head>
<body>
<header class="wrap">
  <div class="head-l">
    <a class="logo" href="/">GeoCareers</a>
    <a class="support" href="${SUPPORT}" target="_blank" rel="noopener"><span aria-hidden="true">🐍</span>${esc(L.support)}</a>
  </div>
  <nav aria-label="${lang === 'de' ? 'Hauptmenü' : 'Main'}">
    ${L.nav.map(([t, h]) => `<a href="${h}">${esc(t)}</a>`).join('\n    ')}
    <a class="ghost" href="${FEEDBACK}" target="_blank" rel="noopener">${esc(L.feedback)}</a>
  </nav>
  <a class="lang" href="${other.replace(SITE, '')}" hreflang="${L.other}" lang="${L.other}" aria-label="${esc(L.switchAria)}">${esc(L.switchLabel)}</a>
</header>
<main class="wrap">
  <section>
    <p class="eyebrow">${esc(L.eyebrow)}</p>
    <h1>${L.h1(c)}</h1>
    <p class="intro">${esc(L.intro(c, s, sec))}</p>
    ${s.tools.length ? `<div class="tags">${s.tools.map(t => `<span class="tag">${esc(t)}</span>`).join('')}</div>` : ''}
    <a class="cta" href="${mapUrl}">${esc(L.cta(s))} →</a>
  </section>
  <section class="box" aria-labelledby="list-h">
    <div class="box-head"><span id="list-h">${esc(L.listTitle(s))}</span><span>${esc(L.name(c))}</span></div>
    <ul class="list">
      ${s.teaser.map(e => `<li><span class="e-name">${esc(e.name)}</span><span class="e-sector">${esc(sectorParts(e.sector).map(L.sector).join(' / '))}</span></li>`).join('\n      ')}
      ${s.n > s.teaser.length ? `<li><a class="more" href="${mapUrl}">${esc(L.more(s.n - s.teaser.length))} →</a></li>` : ''}
    </ul>
  </section>
  ${others.length ? `<section aria-labelledby="cities-h">
    <h2 id="cities-h">${esc(L.others)}</h2>
    <div class="cities">${others.map(x => `<a href="${pageUrl(x, lang).replace(SITE, '')}">${esc(L.name(x))}</a>`).join('')}</div>
  </section>` : ''}
</main>
<footer class="wrap">
  <span><a href="${FEEDBACK}" target="_blank" rel="noopener">${esc(L.feedback)}</a> · <a href="${SUPPORT}" target="_blank" rel="noopener">${esc(L.support)}</a></span>
  <a class="mark" href="/">geocareers.app</a>
</footer>
</body>
</html>
`;
}

// ── Build ────────────────────────────────────────────────────────────────────────────
const rows = await loadRows();
const stats = new Map(CITIES.map(c => [c, cityStats(rows, c)]));
const ready = new Set(CITIES.filter(c => stats.get(c).n > 0));
const sitemap = [`${SITE}/`];
for (const c of ready) {
  const s = stats.get(c);
  for (const lang of ['de', 'en']) {
    const dir = path.join(OUT, lang, lang === 'de' ? c.slugDe : c.slugEn);
    fs.mkdirSync(dir, { recursive: true });
    fs.writeFileSync(path.join(dir, 'index.html'), page(c, lang, s, ready));
    if (s.n >= INDEX_MIN) sitemap.push(pageUrl(c, lang));
  }
  console.log(`${c.de.padEnd(11)} ${String(s.n).padStart(3)} employers  /de/${c.slugDe}  /en/${c.slugEn}${s.n < INDEX_MIN ? '  (noindex)' : ''}`);
}
for (const c of CITIES) if (!ready.has(c)) console.log(`${c.de.padEnd(11)}   0 employers  (no page)`);

fs.mkdirSync(OUT, { recursive: true });
fs.writeFileSync(path.join(OUT, 'sitemap.xml'), `<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
${sitemap.map(u => `  <url>\n    <loc>${u}</loc>\n    <lastmod>${today}</lastmod>\n  </url>`).join('\n')}
</urlset>
`);
console.log(`sitemap.xml: ${sitemap.length} URLs`);
