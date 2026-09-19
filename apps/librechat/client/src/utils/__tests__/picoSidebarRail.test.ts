import { isPicoNavItemActive } from '../picoSidebarRail';

describe('isPicoNavItemActive', () => {
  it('highlights only 我的文件 when the files rail is open on /capability', () => {
    expect(isPicoNavItemActive('/capability', 'files', 'files')).toBe(true);
    expect(isPicoNavItemActive('/capability', 'capability', 'files')).toBe(false);
    expect(isPicoNavItemActive('/capability', 'search', 'files')).toBe(false);
    expect(isPicoNavItemActive('/capability', 'school', 'files')).toBe(false);
  });

  it('highlights only 技能与连接器 on the hub when the chat rail is selected', () => {
    expect(isPicoNavItemActive('/capability', 'capability', 'chats')).toBe(true);
    expect(isPicoNavItemActive('/skills', 'capability', 'chats')).toBe(true);
    expect(isPicoNavItemActive('/capability', 'files', 'chats')).toBe(false);
  });

  it('highlights only 我的文件 on a chat path', () => {
    expect(isPicoNavItemActive('/c/new', 'files', 'files')).toBe(true);
    expect(isPicoNavItemActive('/c/new', 'capability', 'files')).toBe(false);
    expect(isPicoNavItemActive('/c/abc', 'school', 'school')).toBe(true);
    expect(isPicoNavItemActive('/c/abc', 'files', 'school')).toBe(false);
  });
});
