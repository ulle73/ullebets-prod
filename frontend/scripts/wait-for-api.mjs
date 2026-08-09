const healthUrl = "http://127.0.0.1:8787/api/v1/health";
const deadline = Date.now() + 30_000;
let lastError = "API did not become ready";

async function fetchComplete(url) {
  const response = await fetch(url, {
    cache: "no-store",
    signal: AbortSignal.timeout(10_000),
  });
  await response.arrayBuffer();
  return response;
}

while (Date.now() < deadline) {
  try {
    const response = await fetchComplete(healthUrl);
    if (response.ok) {
      const today = new Intl.DateTimeFormat("sv-SE", {
        timeZone: "Europe/Stockholm",
      }).format(new Date());
      const dashboard = await fetchComplete(
        `http://127.0.0.1:8787/api/v1/dashboard?date=${today}`,
      );
      if (dashboard.ok) {
        process.exit(0);
      }
      lastError = `Dashboard warmup returned HTTP ${dashboard.status}`;
    } else {
      lastError = `Healthcheck returned HTTP ${response.status}`;
    }
  } catch (error) {
    lastError = error instanceof Error ? error.message : String(error);
  }

  await new Promise((resolve) => setTimeout(resolve, 250));
}

console.error(`Read API readiness failed: ${lastError}`);
process.exit(1);
