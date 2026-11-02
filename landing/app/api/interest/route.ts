// "Register interest" (landing step 2): the form posts here, and this passes it on to the
// API's public endpoint. The browser only ever talks to this site. The API address is read
// when the request comes in (API_URL), so one build works locally and on Render.
import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";

const FIELDS = ["full_name", "email", "phone", "organisation", "role", "message"] as const;
const TIMEOUT_MS = 15_000; // a sleeping free API takes a while to wake

function reply(status: number, message?: string) {
  return NextResponse.json(message ? { message } : { ok: true }, { status });
}

export async function POST(request: Request) {
  const sent = await request.json().catch(() => null);
  if (!sent || typeof sent !== "object") return reply(400, "Please fill in the form.");

  // Only the form's own fields go on; empty optional ones are left out.
  const body: Record<string, string> = {};
  for (const field of FIELDS) {
    const value = (sent as Record<string, unknown>)[field];
    if (typeof value === "string" && value.trim()) body[field] = value.trim();
  }

  const api = (process.env.API_URL || "http://localhost:8000").replace(/\/$/, "");
  let answer: Response;
  try {
    answer = await fetch(`${api}/api/v1/public/interest`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      cache: "no-store",
      signal: AbortSignal.timeout(TIMEOUT_MS),
    });
  } catch {
    return reply(502, "We could not send it just now. Please try again in a minute.");
  }

  if (answer.ok) return reply(201);
  if (answer.status === 422) return reply(422, "Please check your name, email and clinic.");
  if (answer.status === 429) return reply(429, "You have sent this a few times already. We will be in touch.");
  return reply(502, "We could not send it just now. Please try again in a minute.");
}
