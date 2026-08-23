const PICO_MEMBER_RE = /^[A-Za-z0-9_-]{1,128}$/;

export type PicoMembershipUser = {
  id?: string;
  _id?: string;
  eduId?: string;
  eduSchoolId?: string;
};

/**
 * Prompt 【Pico-User】 must match X-Pico-Membership-Id (school:edu after #625).
 * Do not stamp the LibreChat user id — pico-api treats that as a competing key.
 * Keep in lockstep with packages/api `picoMembershipFromUser` edu branch.
 */
export function picoPromptUserMarker(user?: PicoMembershipUser | null): string {
  const eduId = String(user?.eduId || '').trim();
  const schoolId = String(user?.eduSchoolId || '').trim();
  if (PICO_MEMBER_RE.test(eduId) && PICO_MEMBER_RE.test(schoolId)) {
    return `${schoolId}:${eduId}`;
  }
  if (PICO_MEMBER_RE.test(eduId)) {
    return eduId;
  }
  return '';
}
