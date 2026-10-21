import { NextResponse } from "next/server";
import { z } from "zod";

import { BackendRejectedError, callBackend } from "@/lib/server/backend";
import { isSameOrigin } from "@/lib/server/origin";
import { patientSession } from "@/lib/server/session";

/*
 * Patient sign-in and sign-out (Week 9). The patient never holds the token: like the
 * staff session it lives in an httpOnly cookie, a separate one.
 *
 * POST {step: "start", ...}  asks the API to text a code (the same answer either way).
 * POST {step: "finish", ...} checks the code and sets the patient cookie.
 * DELETE                     signs out.
 */

const details = {
  clinic_id: z.string().uuid(),
  phone: z.string().trim().min(5).max(40),
  date_of_birth: z.string().regex(/^\d{4}-\d{2}-\d{2}$/),
};
const formSchema = z.discriminatedUnion("step", [
  z.object({ step: z.literal("start"), ...details }),
  z.object({ step: z.literal("finish"), ...details, code: z.string().trim().min(4).max(10) }),
]);
const startAnswer = z.object({ message: z.string(), development_code: z.string().nullable() });
const tokenAnswer = z.object({ access_token: z.string() });

// Personal answers must never be stored by a browser or a middleman.
function reply(body: unknown, status = 200) {
  return NextResponse.json(body, { status, headers: { "Cache-Control": "no-store" } });
}

export async function POST(request: Request) {
  if (!isSameOrigin(request)) {
    return reply({ message: "Request refused." }, 403);
  }
  const form = formSchema.safeParse(await request.json().catch(() => null));
  if (!form.success) {
    return reply({ message: "Enter your phone number and date of birth." }, 422);
  }
  const { step, ...body } = form.data;
  const call = { method: "POST", headers: { "Content-Type": "application/json" } };

  try {
    if (step === "start") {
      const answer = await callBackend("/patient-portal/sign-in/start", startAnswer, {
        ...call,
        body: JSON.stringify(body),
      });
      return reply(answer);
    }
    const token = await callBackend("/patient-portal/sign-in/finish", tokenAnswer, {
      ...call,
      body: JSON.stringify(body),
    });
    await patientSession.write(token.access_token);
    return reply({ ok: true });
  } catch (error) {
    if (error instanceof BackendRejectedError && error.status === 401) {
      return reply({ message: "That code is not right, or has expired." }, 401);
    }
    if (error instanceof BackendRejectedError && error.status === 503) {
      return reply({ message: "The code could not be sent. Please try again." }, 503);
    }
    return reply({ message: "The service is unavailable. Please try again." }, 502);
  }
}

export async function DELETE(request: Request) {
  if (!isSameOrigin(request)) {
    return reply({ message: "Request refused." }, 403);
  }
  await patientSession.clear();
  return reply({ ok: true });
}
