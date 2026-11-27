// data-schield: serves the GeoCareers map data from Cloudflare KV to the website only,
// and accepts employer suggestions from the website's Suggest page.
//
// To make copying the whole dataset harder, the data is split:
//   GET /                 the list the map, search and filters need (no descriptions, addresses or links)
//   GET /employer/3,17    the full details of up to 5 employers, loaded when a profile is opened
//   GET /go/3             redirects to employer 3's careers page (used by the Employers table)
// Details and redirects are rate limited per visitor (RATE_DETAIL), the list too (RATE_LIST).
// The workbook and caches are stored in the same KV namespace but are never served.
const ALLOWED_ORIGINS = [
  "https://geocareers.app",
  "https://www.geocareers.app",
  "https://geo-careers.natashlazar-pro.workers.dev",
];

// Suggestions are stored as KV keys "suggestions/<time>-<random>" (one JSON object each).
const SUGGESTION_PREFIX = "suggestions/";
const MAX_PER_IP_PER_DAY = 10;
const LIMITS = { company: 150, city: 80, careers_url: 400, tools: 300, note: 1500 };

// Fields sent in the list; everything else only comes through /employer/<i>.
const LIST_FIELDS = ["c_name", "c_url", "city", "sector", "g_role", "g_stack", "size", "kununu_rate", "sprach", "first_seen", "lon", "lat"];
const DETAIL_FIELDS = ["c_name", "adress", "postal_code", "kp_url", "kununu_url", "li_url", "eng", "de"];
const MAX_IDS = 5;

// companies.json parsed once per Worker instance for a minute, instead of on every request
let cache = { at: 0, rows: [] };
async function rows(env) {
  if (Date.now() - cache.at < 60_000) return cache.rows;
  const raw = await env.DATA.get("companies.json", { cacheTtl: 300 });
  let list = [];
  try { list = JSON.parse(raw || "[]"); } catch { list = []; }
  cache = { at: Date.now(), rows: Array.isArray(list) ? list : [] };
  return cache.rows;
}
const pick = (row, fields) => Object.fromEntries(fields.filter((f) => row[f] !== undefined && row[f] !== "").map((f) => [f, row[f]]));

// Cloudflare rate-limit bindings (see wrangler.template.jsonc); without them nothing is limited.
async function allowed(limiter, request) {
  if (!limiter) return true;
  const ip = request.headers.get("CF-Connecting-IP") || "unknown";
  try { return (await limiter.limit({ key: ip })).success; } catch { return true; }
}
const tooMany = (cors) => new Response("Too many requests", { status: 429, headers: { ...cors, "Retry-After": "60" } });

export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    // Careers-page redirect: a normal link click sends no Origin header, so check the Referer instead.
    if (request.method === "GET" && url.pathname.startsWith("/go/")) {
      return handleGo(request, env, url);
    }

    const origin = request.headers.get("Origin") || "";
    if (!ALLOWED_ORIGINS.includes(origin)) {
      return new Response("Forbidden", { status: 403 });
    }
    const cors = { "Access-Control-Allow-Origin": origin, "Vary": "Origin" };

    if (request.method === "OPTIONS") {
      return new Response(null, {
        headers: {
          ...cors,
          "Access-Control-Allow-Methods": "GET, POST",
          "Access-Control-Allow-Headers": "Content-Type",
          "Access-Control-Max-Age": "86400",
        },
      });
    }

    if (request.method === "POST" && url.pathname === "/suggest") {
      return handleSuggestion(request, env, cors);
    }

    if (request.method !== "GET") {
      return new Response("Method not allowed", { status: 405, headers: cors });
    }
    if (url.pathname.startsWith("/employer/")) {
      if (!(await allowed(env.RATE_DETAIL, request))) return tooMany(cors);
      const ids = url.pathname.slice("/employer/".length).split(",").slice(0, MAX_IDS)
        .map((x) => Number(x)).filter((x) => Number.isInteger(x) && x >= 0);
      const all = await rows(env);
      const out = ids.filter((i) => i < all.length).map((i) => ({ i, ...pick(all[i], DETAIL_FIELDS) }));
      return new Response(JSON.stringify(out), {
        headers: { ...cors, "Content-Type": "application/json; charset=utf-8", "Cache-Control": "private, max-age=300" },
      });
    }

    if (url.pathname !== "/") return new Response("Not found", { status: 404, headers: cors });
    if (!(await allowed(env.RATE_LIST, request))) return tooMany(cors);
    const list = (await rows(env)).map((row, i) => ({ i, ...pick(row, LIST_FIELDS), ...(row.kp_url ? { jobs: 1 } : {}) }));
    return new Response(JSON.stringify(list), {
      headers: { ...cors, "Content-Type": "application/json; charset=utf-8", "Cache-Control": "private, max-age=300" },
    });
  },
};

async function handleGo(request, env, url) {
  const referer = request.headers.get("Referer") || "";
  if (!ALLOWED_ORIGINS.some((o) => referer === o || referer.startsWith(o + "/"))) {
    return new Response("Forbidden", { status: 403 });
  }
  if (!(await allowed(env.RATE_DETAIL, request))) return tooMany({});
  const i = Number(url.pathname.slice("/go/".length));
  const row = Number.isInteger(i) && i >= 0 ? (await rows(env))[i] : null;
  let target = row && String(row.kp_url || "").trim();
  if (target && !/^https?:\/\//i.test(target)) target = "https://" + target;
  try { target = target && new URL(target).href; } catch { target = ""; }
  if (!target) return new Response("Not found", { status: 404 });
  return new Response(null, { status: 302, headers: { Location: target, "Cache-Control": "no-store", "Referrer-Policy": "no-referrer" } });
}

function json(body, status, cors) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { ...cors, "Content-Type": "application/json; charset=utf-8", "Cache-Control": "no-store" },
  });
}

function clean(value, max) {
  return String(value ?? "").replace(/[\u0000-\u0008\u000b-\u001f\u007f]/g, "").trim().slice(0, max);
}

async function handleSuggestion(request, env, cors) {
  if (Number(request.headers.get("Content-Length") || 0) > 8192) {
    return json({ ok: false, error: "too_large" }, 413, cors);
  }
  let body;
  try {
    body = await request.json();
  } catch {
    return json({ ok: false, error: "bad_json" }, 400, cors);
  }

  // Honeypot: real visitors never see or fill the "website" field.
  if (clean(body.website, 200)) return json({ ok: true }, 200, cors);

  const s = {
    company: clean(body.company, LIMITS.company),
    city: clean(body.city, LIMITS.city),
    careers_url: clean(body.careers_url, LIMITS.careers_url),
    tools: clean(body.tools, LIMITS.tools),
    note: clean(body.note, LIMITS.note),
    lang: body.lang === "en" ? "en" : "de",
  };
  if (!s.company || !s.city) return json({ ok: false, error: "missing_fields" }, 400, cors);
  if (s.careers_url) {
    if (!/^https?:\/\//i.test(s.careers_url)) s.careers_url = "https://" + s.careers_url;
    try { new URL(s.careers_url); } catch { return json({ ok: false, error: "bad_url" }, 400, cors); }
  }

  // Simple rate limit per visitor IP (hashed, so no raw IPs are stored).
  const ip = request.headers.get("CF-Connecting-IP") || "unknown";
  const day = new Date().toISOString().slice(0, 10);
  const ipHash = await sha256(`${ip}|${day}`);
  const rateKey = `ratelimit/suggest/${ipHash}`;
  const used = Number((await env.DATA.get(rateKey)) || 0);
  if (used >= MAX_PER_IP_PER_DAY) return json({ ok: false, error: "rate_limited" }, 429, cors);
  await env.DATA.put(rateKey, String(used + 1), { expirationTtl: 60 * 60 * 26 });

  const now = new Date().toISOString();
  const id = `${now.replace(/[:.]/g, "-")}-${crypto.randomUUID().slice(0, 8)}`;
  const record = { id, received_at: now, status: "new", ...s };
  await env.DATA.put(SUGGESTION_PREFIX + id, JSON.stringify(record));
  await notify(env, record);
  return json({ ok: true, id }, 201, cors);
}

// Emails the suggestion to the inbox in the NOTIFY_TO secret (a verified Email Routing
// destination address). A failed email never loses the suggestion: it is already saved in KV.
async function notify(env, r) {
  if (!env.NOTIFY || !env.NOTIFY_TO) return;
  const lines = [
    `Company:      ${r.company}`,
    `City:         ${r.city}`,
    `Careers page: ${r.careers_url || "-"}`,
    `Tools:        ${r.tools || "-"}`,
    `Note:         ${r.note || "-"}`,
    `Page language: ${r.lang.toUpperCase()}`,
    "",
    `Received ${r.received_at}. Saved in KV as ${SUGGESTION_PREFIX}${r.id}`,
  ];
  try {
    await env.NOTIFY.send({
      from: env.NOTIFY_FROM || "suggestions@geocareers.app",
      to: env.NOTIFY_TO,
      subject: `GeoCareers suggestion: ${r.company} (${r.city})`.slice(0, 180),
      text: lines.join("\n"),
    });
  } catch (err) {
    console.error("Suggestion email failed:", err && err.message ? err.message : err);
  }
}

async function sha256(text) {
  const buf = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(text));
  return [...new Uint8Array(buf)].map((b) => b.toString(16).padStart(2, "0")).join("").slice(0, 32);
}
