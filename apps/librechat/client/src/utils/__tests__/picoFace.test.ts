import { picoAssistantLabel, picoSkillDesc, picoSkillTitle } from '../picoFace';

describe('picoFace', () => {
  it('maps vendor senders to Pico', () => {
    expect(picoAssistantLabel('OpenAI')).toBe('Pico');
    expect(picoAssistantLabel('Assistant')).toBe('Pico');
    expect(picoAssistantLabel('gpt-5.6-sol')).toBe('Pico');
    expect(picoAssistantLabel('gemini-3.8-flash')).toBe('Pico');
    expect(picoAssistantLabel('')).toBe('Pico');
  });

  it('keeps a custom agent name', () => {
    expect(picoAssistantLabel('文档助理')).toBe('文档助理');
  });

  it('maps skill slugs to Chinese titles', () => {
    expect(picoSkillTitle({ name: 'skill-quiz-draft' })).toBe('出测验草稿');
    expect(picoSkillTitle({ name: 'skill-chat', displayTitle: '闲聊' })).toBe('闲聊');
    expect(picoSkillDesc({ name: 'skill-kb-ask', description: 'Answer from school' })).toBe(
      '只根据已挂材料作答，没有就不编。',
    );
  });
});
