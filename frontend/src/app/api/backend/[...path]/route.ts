import { forwardToBackend } from "@/lib/server/proxy";

// The screens call /api/backend/... and this forwards to the API's /api/v1/...
// All the safety rules live in lib/server/proxy.ts.

type Context = { params: Promise<{ path: string[] }> };

async function handle(request: Request, context: Context) {
  const { path } = await context.params;
  return forwardToBackend(request, path);
}

export const GET = handle;
export const POST = handle;
