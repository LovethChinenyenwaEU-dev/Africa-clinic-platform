export const dynamic = "force-dynamic";

async function getApiStatus(): Promise<string> {
  try {
    const res = await fetch(`${process.env.API_INTERNAL_URL}/health/ready`, {
      cache: "no-store",
    });
    return res.ok ? "connected" : "unavailable";
  } catch {
    return "unavailable";
  }
}

export default async function Home() {
  const status = await getApiStatus();
  return (
    <main style={{ padding: 32, fontFamily: "system-ui, sans-serif" }}>
      <h1>Clinic Platform</h1>
      <p>API status: {status}</p>
    </main>
  );
}
