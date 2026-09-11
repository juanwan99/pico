/** Human copy for school-jump failures. Teachers have no Pico password. */
const SSO_LOGIN_COPY: Record<string, string> = {
  expired: '学校跳转已过期。请回学校再点一次进入工作台。',
  used: '这张跳转链接已经用过。请回学校再点一次进入工作台。',
  missing: '没有跳转票据。请从学校入口进入工作台。',
  upstream: '工作台暂时连不上学校登录。请稍后再从学校进入。',
  invalid: '学校跳转未成功。请回学校再点一次进入工作台。',
};

export function getSsoLoginMessage(reason: string | null | undefined): string {
  const key = String(reason || '').trim();
  if (!key) {
    return '';
  }
  return SSO_LOGIN_COPY[key] || SSO_LOGIN_COPY.invalid;
}
