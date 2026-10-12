"use client";

export default function ErrorPage({ reset }: { reset: () => void }) {
  return (
    <main className="page">
      <h1>Something went wrong</h1>
      <p>The service may be unavailable. Please try again.</p>
      <button className="button" type="button" onClick={reset}>
        Try again
      </button>
    </main>
  );
}