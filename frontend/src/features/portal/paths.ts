// The patient pages live under /patient/<clinic ID>/: the clinic ID comes from the
// link the clinic shares, because a patient belongs to one clinic.

const CLINIC_PAGE = /^\/patient\/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})(\/|$)/i;

/** Where to sign in again from this page: the clinic's patient sign-in, or the staff login. */
export function signInPageFor(pathname: string): string {
  const match = CLINIC_PAGE.exec(pathname);
  return match ? `/patient/${match[1]}` : "/login";
}

export function patientHome(clinicId: string): string {
  return `/patient/${clinicId}/home`;
}
