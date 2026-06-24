// Duennes Relay: Telegram-Webhook -> GitHub repository_dispatch.
//
// KEINE Approve/Reject-Logik hier. Die Single-Source-of-Truth bleibt
// scripts/telegram_check.py:process_update(), das im Actions-Workflow
// telegram-webhook.yml laeuft. Diese Function prueft nur den geheimen
// Header und reicht das Telegram-Update an GitHub Actions weiter.
//
// Kein npm-Paket noetig: globales fetch + Netlify.env (Node-Runtime auf Netlify).

export default async (req: Request): Promise<Response> => {
  if (req.method !== "POST") {
    return new Response("Method Not Allowed", { status: 405 });
  }

  // Faelschungsschutz: Telegram sendet den bei setWebhook hinterlegten
  // secret_token in diesem Header. Mismatch -> nicht weiterleiten.
  const expected = Netlify.env.get("TELEGRAM_WEBHOOK_SECRET");
  const got = req.headers.get("x-telegram-bot-api-secret-token");
  if (!expected || got !== expected) {
    return new Response("Forbidden", { status: 401 });
  }

  let update: unknown;
  try {
    update = await req.json();
  } catch {
    return new Response("Bad Request", { status: 400 });
  }

  const repo = Netlify.env.get("GH_DISPATCH_REPO"); // z.B. "erriionn/insektenblitz"
  const token = Netlify.env.get("GH_DISPATCH_PAT");
  if (!repo || !token) {
    // Fehlkonfiguration: 503 (von einem GitHub-Dispatch-Fehler unterscheidbar).
    console.error(
      `relay misconfig: hasRepo=${!!repo} hasToken=${!!token}`,
    );
    return new Response("Server misconfigured", { status: 503 });
  }

  const ghRes = await fetch(`https://api.github.com/repos/${repo}/dispatches`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      Accept: "application/vnd.github+json",
      "X-GitHub-Api-Version": "2022-11-28",
      "User-Agent": "insektenblitz-telegram-webhook",
    },
    body: JSON.stringify({
      event_type: "telegram-update",
      client_payload: { update },
    }),
  });

  // GitHub antwortet 204 bei Erfolg. Bei Fehler den ECHTEN GitHub-Status
  // durchreichen (403 = PAT-Rechte, 404 = Repo/Access falsch, 422 = Payload),
  // damit getWebhookInfo den Grund zeigt. Nicht-2xx -> Telegram stellt erneut zu.
  if (!ghRes.ok) {
    const detail = (await ghRes.text()).slice(0, 300);
    console.error(`github dispatch failed: ${ghRes.status} ${detail}`);
    return new Response(`Dispatch failed: ${ghRes.status}`, {
      status: ghRes.status,
    });
  }
  return new Response("OK", { status: 200 });
};

export const config = {
  path: "/telegram-webhook",
};
