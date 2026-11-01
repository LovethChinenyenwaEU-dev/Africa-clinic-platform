import { redirect } from "next/navigation";

// "Staff sign in" on the page leads here, then to the clinic app's sign-in page. The address
// is read when the request comes in (APP_URL), not baked into the build, so the same image
// works locally (http://localhost:3000) and on Render.
export const dynamic = "force-dynamic";

export function GET() {
  const app = (process.env.APP_URL || "http://localhost:3000").replace(/\/$/, "");
  redirect(`${app}/login`);
}
