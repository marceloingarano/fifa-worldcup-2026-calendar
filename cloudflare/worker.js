/**
 * Cloudflare Worker — Proxy for FIFA World Cup 2026 Calendar
 *
 * Serves the .ics file from GitHub Pages while enabling Cloudflare Analytics.
 * Deploy at: copa2026.trakas.com.br
 *
 * What it does:
 * 1. Receives request for the .ics file
 * 2. Fetches from GitHub Pages (origin)
 * 3. Returns the file with correct headers
 * 4. Cloudflare automatically logs the request (analytics dashboard)
 */

const GITHUB_PAGES_ORIGIN = "https://marceloingarano.github.io/fifa-worldcup-2026-calendar";

export default {
  async fetch(request) {
    const url = new URL(request.url);
    const path = url.pathname;

    // Root → serve landing page
    // /fifa-worldcup-2026.ics → serve calendar file
    const originUrl = `${GITHUB_PAGES_ORIGIN}${path === "/" ? "/index.html" : path}`;

    const response = await fetch(originUrl, {
      headers: {
        "User-Agent": "Cloudflare-Worker-Copa2026",
      },
    });

    if (!response.ok) {
      return new Response("Not Found", { status: 404 });
    }

    const headers = new Headers(response.headers);

    // Set correct content type for .ics
    if (path.endsWith(".ics")) {
      headers.set("Content-Type", "text/calendar; charset=utf-8");
      headers.set("Content-Disposition", 'attachment; filename="fifa-worldcup-2026.ics"');
    }

    // Cache for 6 hours (matches calendar refresh interval)
    headers.set("Cache-Control", "public, max-age=21600");

    // CORS for web access
    headers.set("Access-Control-Allow-Origin", "*");

    return new Response(response.body, {
      status: response.status,
      headers,
    });
  },
};
