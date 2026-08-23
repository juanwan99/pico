import { act, renderHook } from '@testing-library/react';
import { useRecoilValue, useSetRecoilState } from 'recoil';
import { useChatContext, useChatFormContext, useAddedChatContext } from '~/Providers';
import { useGetLatestMessage } from '~/hooks/Messages/useLatestMessage';
import { useAuthContext } from '~/hooks/AuthContext';
import useSubmitMessage from '../useSubmitMessage';

const mockSetActivePrompt = jest.fn();

jest.mock('recoil', () => ({
  useRecoilValue: jest.fn(),
  useSetRecoilState: jest.fn(),
}));

jest.mock('librechat-data-provider', () => ({
  replaceSpecialVars: jest.fn(({ text }) => text),
}));

jest.mock('~/Providers', () => ({
  useChatContext: jest.fn(),
  useChatFormContext: jest.fn(),
  useAddedChatContext: jest.fn(),
}));

jest.mock('~/hooks/AuthContext', () => ({
  useAuthContext: jest.fn(),
}));

jest.mock('~/hooks/Messages/useLatestMessage', () => ({
  useGetLatestMessage: jest.fn(),
}));

jest.mock('~/store', () => ({
  __esModule: true,
  default: {
    autoSendPrompts: 'autoSendPrompts',
    activePromptByIndex: jest.fn(() => 'activePromptByIndex'),
  },
}));

const mockUseRecoilValue = useRecoilValue as jest.Mock;
const mockUseSetRecoilState = useSetRecoilState as jest.Mock;
const mockUseChatContext = useChatContext as jest.Mock;
const mockUseChatFormContext = useChatFormContext as jest.Mock;
const mockUseAddedChatContext = useAddedChatContext as jest.Mock;
const mockUseAuthContext = useAuthContext as jest.Mock;
const mockUseGetLatestMessage = useGetLatestMessage as jest.Mock;

describe('useSubmitMessage', () => {
  const ask = jest.fn();
  const reset = jest.fn();
  const setMessages = jest.fn();
  const getMessages = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
    localStorage.clear();
    sessionStorage.clear();
    window.history.replaceState({}, '', '/c/new');
    mockUseRecoilValue.mockReturnValue(false);
    mockUseSetRecoilState.mockReturnValue(mockSetActivePrompt);
    mockUseAuthContext.mockReturnValue({ user: { id: 'user-1' } });
    mockUseAddedChatContext.mockReturnValue({ conversation: null });
    mockUseChatFormContext.mockReturnValue({ reset, getValues: jest.fn(() => '') });
    mockUseGetLatestMessage.mockReturnValue(() => ({ messageId: 'assistant-message' }));
    getMessages.mockReturnValue([{ messageId: 'assistant-message' }]);
    mockUseChatContext.mockReturnValue({
      ask,
      index: 0,
      getMessages,
      setMessages,
    });
  });

  it('propagates blocked submits so direct callers can preserve their text', () => {
    ask.mockReturnValue(false);

    const { result } = renderHook(() => useSubmitMessage());

    let submitted: false | void = undefined;
    act(() => {
      submitted = result.current.submitMessage({ text: 'dictated follow-up' });
    });

    expect(submitted).toBe(false);
    expect(reset).not.toHaveBeenCalled();
  });

  it('reads the tail at call time and appends it to root when missing', () => {
    const rootMessages = [{ messageId: 'root-user' }];
    const latest = { messageId: 'assistant-tail', text: 'tail' };
    const reader = jest.fn(() => latest);
    mockUseGetLatestMessage.mockReturnValue(reader);
    getMessages.mockReturnValue(rootMessages);
    ask.mockReturnValue(true);

    const { result } = renderHook(() => useSubmitMessage());
    act(() => {
      result.current.submitMessage({ text: 'hello' });
    });

    expect(reader).toHaveBeenCalled();
    expect(setMessages).toHaveBeenCalledWith([...rootMessages, latest]);
    expect(ask).toHaveBeenCalled();
    expect(reset).toHaveBeenCalled();
  });

  it('does not append when the latest message is already in root', () => {
    const latest = { messageId: 'assistant-tail' };
    mockUseGetLatestMessage.mockReturnValue(() => latest);
    getMessages.mockReturnValue([latest]);
    ask.mockReturnValue(true);

    const { result } = renderHook(() => useSubmitMessage());
    act(() => {
      result.current.submitMessage({ text: 'hello' });
    });

    expect(setMessages).not.toHaveBeenCalled();
    expect(ask).toHaveBeenCalled();
  });

  it('does not append when there is no latest message', () => {
    mockUseGetLatestMessage.mockReturnValue(() => null);
    getMessages.mockReturnValue([{ messageId: 'root-user' }]);
    ask.mockReturnValue(true);

    const { result } = renderHook(() => useSubmitMessage());
    act(() => {
      result.current.submitMessage({ text: 'hello' });
    });

    expect(setMessages).not.toHaveBeenCalled();
    expect(ask).toHaveBeenCalled();
  });

  it('adds auditable project bindings to a project-scoped submission', () => {
    mockUseChatContext.mockReturnValue({
      ask,
      index: 0,
      getMessages,
      setMessages,
      conversation: {
        conversationId: 'new',
        chatProjectId: 'project-1',
      },
    });
    localStorage.setItem('pico:projectInstruction:project-1', '先给结论，再列风险');
    localStorage.setItem(
      'pico:projectBindings:project-1',
      JSON.stringify({
        expert: '研究分析',
        skill: '会议纪要',
        connector: 'MCP 通用',
      }),
    );
    ask.mockReturnValue(true);

    const { result } = renderHook(() => useSubmitMessage());
    act(() => {
      result.current.submitMessage({ text: '分析这份材料' });
    });

    const submittedText = ask.mock.calls[0][0].text as string;
    expect(submittedText).toContain('【项目上下文（可审计）】');
    expect(submittedText).toContain('项目指令：先给结论，再列风险');
    expect(submittedText).toContain('绑定专家：研究分析');
    expect(submittedText).toContain('绑定技能：会议纪要');
    expect(submittedText).toContain('绑定连接器：MCP 通用');
    expect(submittedText).toContain('不得视为已连接、已授权或可调用工具');
    expect(submittedText).toContain('仅可使用本会话中已真实配置并授权的工具');
    expect(submittedText).toMatch(/分析这份材料$/);
  });

  it('does not read connector drafts or expose secret-like binding values', () => {
    mockUseChatContext.mockReturnValue({
      ask,
      index: 0,
      getMessages,
      setMessages,
      conversation: {
        conversationId: 'new',
        chatProjectId: 'project-1',
      },
    });
    localStorage.setItem(
      'pico:projectBindings:project-1',
      JSON.stringify({
        expert: '研究分析',
        connector: 'api_key=do-not-submit',
      }),
    );
    localStorage.setItem(
      'pico:connectorDraft:c1:default',
      JSON.stringify({ endpoint: 'https://private.example', token: 'draft-secret' }),
    );
    ask.mockReturnValue(true);

    const { result } = renderHook(() => useSubmitMessage());
    act(() => {
      result.current.submitMessage({ text: 'hello' });
    });

    const submittedText = ask.mock.calls[0][0].text as string;
    expect(submittedText).toContain('绑定专家：研究分析');
    expect(submittedText).not.toContain('do-not-submit');
    expect(submittedText).not.toContain('private.example');
    expect(submittedText).not.toContain('draft-secret');
  });

  it('ignores a stale active project for a non-project conversation', () => {
    sessionStorage.setItem('pico:activeProjectId', 'stale-project');
    localStorage.setItem('pico:projectInstruction:stale-project', '不应注入');
    localStorage.setItem(
      'pico:projectBindings:stale-project',
      JSON.stringify({ expert: '不应出现' }),
    );
    mockUseChatContext.mockReturnValue({
      ask,
      index: 0,
      getMessages,
      setMessages,
      conversation: {
        conversationId: 'new',
        chatProjectId: null,
      },
    });
    ask.mockReturnValue(true);

    const { result } = renderHook(() => useSubmitMessage());
    act(() => {
      result.current.submitMessage({ text: '普通会话' });
    });

    const submittedText = ask.mock.calls[0][0].text as string;
    expect(submittedText).not.toContain('项目上下文');
    expect(submittedText).not.toContain('不应注入');
    expect(submittedText).not.toContain('不应出现');
    expect(submittedText).toMatch(/普通会话$/);
  });

  it('does not stamp LibreChat user id as Pico-User (header is school:edu)', () => {
    ask.mockReturnValue(true);

    const { result } = renderHook(() => useSubmitMessage());
    act(() => {
      result.current.submitMessage({ text: '普通会话' });
    });

    const submittedText = ask.mock.calls[0][0].text as string;
    expect(submittedText).not.toContain('【Pico-User:user-1】');
  });

  it('stamps school:edu Pico-User when edu tenant keys are on the user', () => {
    mockUseAuthContext.mockReturnValue({
      user: {
        id: 'user-1',
        eduId: 'aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee',
        eduSchoolId: '627bcf3a-a9a8-4047-afcc-3d4878e2a7af',
      },
    });
    ask.mockReturnValue(true);

    const { result } = renderHook(() => useSubmitMessage());
    act(() => {
      result.current.submitMessage({ text: '普通会话' });
    });

    const submittedText = ask.mock.calls[0][0].text as string;
    expect(submittedText).toContain(
      '【Pico-User:627bcf3a-a9a8-4047-afcc-3d4878e2a7af:aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee】',
    );
  });

  it('uses matching URL and active-project context for a newly opened project task', () => {
    sessionStorage.setItem('pico:activeProjectId', 'project-1');
    window.history.replaceState({}, '', '/c/new?projectId=project-1');
    localStorage.setItem(
      'pico:projectBindings:project-1',
      JSON.stringify({ skill: '周报生成' }),
    );
    mockUseChatContext.mockReturnValue({
      ask,
      index: 0,
      getMessages,
      setMessages,
      conversation: {
        conversationId: 'new',
        chatProjectId: null,
      },
    });
    ask.mockReturnValue(true);

    const { result } = renderHook(() => useSubmitMessage());
    act(() => {
      result.current.submitMessage({ text: '开始任务' });
    });

    expect(ask.mock.calls[0][0].text).toContain('绑定技能：周报生成');
  });
});
