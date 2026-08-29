import {
  isUnnamedConvoTitle,
  persistFirstMessageTitle,
  titleFromFirstMessage,
} from '../picoConvoTitle';

describe('picoConvoTitle', () => {
  it('treats New Chat / 新对话 / empty as unnamed', () => {
    expect(isUnnamedConvoTitle('New Chat')).toBe(true);
    expect(isUnnamedConvoTitle('新对话')).toBe(true);
    expect(isUnnamedConvoTitle('')).toBe(true);
    expect(isUnnamedConvoTitle(null)).toBe(true);
    expect(isUnnamedConvoTitle('期末复习计划')).toBe(false);
  });

  it('names from the first user turn and strips Pico 【】 prefixes', () => {
    expect(titleFromFirstMessage('帮我写一份三年级数学复习计划')).toBe(
      '帮我写一份三年级数学复习计划',
    );
    expect(
      titleFromFirstMessage(
        '【Pico-User:school:teacher】\n【权限：默认沙箱】\n帮我写一份三年级数学复习计划',
      ),
    ).toBe('帮我写一份三年级数学复习计划');
    const long = '请根据本学期课表整理一份超长的期末复习安排并且把每一科都写清楚';
    const named = titleFromFirstMessage(long, 12);
    expect(named.endsWith('…')).toBe(true);
    expect(named.length).toBeLessThanOrEqual(13);
  });

  it('persists only unnamed real conversations', async () => {
    const updateTitle = jest.fn().mockResolvedValue({});
    expect(
      persistFirstMessageTitle({
        conversationId: 'c1',
        currentTitle: 'New Chat',
        firstMessage: '写课时计划',
        updateTitle,
      }),
    ).toBe('写课时计划');
    await Promise.resolve();
    expect(updateTitle).toHaveBeenCalledWith('c1', '写课时计划');

    updateTitle.mockClear();
    expect(
      persistFirstMessageTitle({
        conversationId: 'c1',
        currentTitle: '已改过的名字',
        firstMessage: '写课时计划',
        updateTitle,
      }),
    ).toBeNull();
    expect(updateTitle).not.toHaveBeenCalled();

    expect(
      persistFirstMessageTitle({
        conversationId: 'new',
        currentTitle: 'New Chat',
        firstMessage: '写课时计划',
        updateTitle,
      }),
    ).toBeNull();
  });
});
