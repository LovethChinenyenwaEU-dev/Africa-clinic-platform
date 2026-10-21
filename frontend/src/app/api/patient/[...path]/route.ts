import { forwardForPatient } from "@/lib/server/proxy";

// The patient pages call /api/patient/... and this forwards to the API's /patient-portal/...
// with the patient cookie. All the safety rules live in lib/server/proxy.ts.

type Context = { params: Promise<{ path: string[] }> };

async function handle(request: Request, context: Context) {
  const { path } = await context.params;
  return forwardForPatient(request, path);
}

export const GET = handle;
export const POST = handle;
