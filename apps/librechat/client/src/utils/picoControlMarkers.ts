export function stripPicoControlMarkers(text: string): string {
  return text
    .replace(/【Pico-User:[^】]*】\s*/g, '')
    .replace(/【Pico-Convo:[^】]*】\s*/g, '')
    .replace(/【Pico-Skill:[^】]*】\s*/g, '')
    .replace(/【工作空间：[^】]*】(?:（[^）]*）)?\s*/g, '')
    .replace(/【权限：[^】]*】\s*/g, '')
    .replace(/【模型偏好：[^】]*】\s*/g, '')
    .replace(/【项目指令：[^】]*】\s*/g, '')
    .trim();
}
