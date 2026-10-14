import Link from "next/link";

import { navFor } from "@/features/identity/navigation";
import { requireUser } from "@/lib/server/require-user";

export default async function Home() {
  const user = await requireUser();
  const screens = navFor(user.role).filter((item) => item.href !== "/");

  return (
    <section>
      <h1>Welcome, {user.full_name}</h1>
      {screens.length > 0 ? (
        <ul className="grid gap-3 sm:grid-cols-2">
          {screens.map((item) => (
            <li key={item.href}>
              <Link
                href={item.href}
                className="block rounded-lg border border-line bg-white p-4 font-semibold text-accent hover:border-accent"
              >
                {item.label}
              </Link>
            </li>
          ))}
        </ul>
      ) : (
        <p>There are no screens for your role yet.</p>
      )}
    </section>
  );
}
