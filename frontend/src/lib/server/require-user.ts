import "server-only";

import { redirect } from "next/navigation";
import { cache } from "react";

import { canOpen, type ScreenKey } from "@/features/identity/navigation";
import type { Me } from "@/features/identity/schemas";

import { getCurrentUser } from "./current-user";

// One backend call per page load, even when the layout and the page both ask.
const currentUser = cache(getCurrentUser);

/**
 * The signed-in person, for a page that needs one.
 * Nobody signed in: off to /login. Signed in but not allowed here: back home.
 */
export async function requireUser(screen: ScreenKey = "home"): Promise<Me> {
  const user = await currentUser();
  if (!user) {
    redirect("/login");
  }
  if (!canOpen(user.role, screen)) {
    redirect("/");
  }
  return user;
}
