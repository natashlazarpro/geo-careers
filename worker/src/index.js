// data-schield: serves the GeoCareers map data from Cloudflare KV to the website only,
// and accepts employer suggestions from the website's Suggest page.
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

export default {
  async fetch(request, env) {
    const origin = request.headers.get("Origin") || "";
    if (!ALLOWED_ORIGINS.includes(origin)) {
      return new Response("Forbidden", { status: 403 });
    }
    const cors = { "Access-Control-Allow-Origin": origin, "Vary": "Origin" };
    const url = new URL(request.url);

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
    const data = await env.DATA.get("companies.json", { cacheTtl: 300 });
    return new Response(data || "[]", {
      headers: { ...cors, "Content-Type": "application/json; charset=utf-8", "Cache-Control": "public, max-age=300" },
    });
  },
};

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
  await env.DATA.put(SUGGESTION_PREFIX + id, JSON.stringify({ id, received_at: now, status: "new", ...s }));
  return json({ ok: true, id }, 201, cors);
}

async function sha256(text) {
  const buf = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(text));
  return [...new Uint8Array(buf)].map((b) => b.toString(16).padStart(2, "0")).join("").slice(0, 32);
}
