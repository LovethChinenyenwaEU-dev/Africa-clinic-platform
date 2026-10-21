import Link from "next/link";

import { can } from "@/features/identity/abilities";
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
      {can(user.role, "register_patient") && (
        <div className="card mt-6 grid gap-1">
          <h2 className="mb-0 text-lg">Patient web page</h2>
          <p className="text-sm">
            Give patients this address (or print it as a QR code). They sign in with their
            phone number, date of birth and a code sent by SMS.
          </p>
          <p className="break-all font-mono">{`/patient/${user.tenant_id}`}</p>
        </div>
      )}
    </section>
  );
}
