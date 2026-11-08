// data-schield: serves the GeoCareers map data from Cloudflare KV to the website only.
// The workbook and caches are stored in the same KV namespace but are never served.
const ALLOWED_ORIGINS = [
  "https://geocareers.app",
  "https://www.geocareers.app",
  "https://geo-careers.natashlazar-pro.workers.dev",
];

export default {
  async fetch(request, env) {
    const origin = request.headers.get("Origin") || "";
    if (!ALLOWED_ORIGINS.includes(origin)) {
      return new Response("Forbidden", { status: 403 });
    }
    const cors = { "Access-Control-Allow-Origin": origin, "Vary": "Origin" };
    if (request.method === "OPTIONS") {
      return new Response(null, { headers: { ...cors, "Access-Control-Allow-Methods": "GET" } });
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
