import { z } from "zod";

import { wordingSchema, type Purpose, type Wording } from "@/features/consent/schemas";
import { branchSchema, type Branch } from "@/features/scheduling/schemas";
import { apiPost } from "@/lib/api-client";

/*
 * Clinic settings (Week 11), for admins: the clinic's branches and the consent wording
 * patients agree to. Reading uses the existing calls (getBranches, getCurrentWording).
 */

export const MAX_WORDING_LENGTH = 5000; // the backend's limit

export const newBranchSchema = z.object({
  name: z.string().trim().min(1, "Enter the branch name.").max(120, "At most 120 characters."),
  city: z.string().trim().max(120, "At most 120 characters."),
});
export type NewBranch = z.infer<typeof newBranchSchema>;

export function addBranch(branch: NewBranch): Promise<Branch> {
  return apiPost("/tenancy/branches", branch, branchSchema);
}

/** A problem with new wording, or null. Publishing the same words again is pointless. */
export function wordingProblem(body: string, current: Wording | null): string | null {
  const clean = body.trim();
  if (!clean) return "Write the wording patients will agree to.";
  if (clean.length > MAX_WORDING_LENGTH) return `At most ${MAX_WORDING_LENGTH} characters.`;
  if (current && clean === current.body.trim()) return "This is the wording already in use.";
  return null;
}

/** Publish new wording: it becomes the next version. Consents already given keep theirs. */
export function publishWording(purpose: Purpose, body: string): Promise<Wording> {
  return apiPost("/consent/texts", { purpose, body: body.trim() }, wordingSchema);
}
