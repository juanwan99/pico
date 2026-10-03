import { processStepLines } from '../usePicoTaskLedger';

const ev = (seq: number, type: string, payload: Record<string, unknown>) => ({
  id: `e${seq}`,
  run_id: 'r1',
  seq,
  type,
  payload,
});

describe('processStepLines (#1169)', () => {
  it('lists each step once, drafting then call updating one line in place', () => {
    const lines = processStepLines([
      ev(1, 'agent.step', { step: 1, phase: 'model' }),
      ev(2, 'tool.call', { tool: 'read', step_line: '正在读 秋天的雨.docx' }),
      ev(3, 'tool.result', { tool: 'read', ok: true }),
      ev(4, 'tool.drafting', { tool: 'write', step_line: '正在写文件…' }),
      ev(5, 'tool.drafting', { tool: 'write', step_line: '正在写文件（已写 12 KB）' }),
      ev(6, 'tool.call', { tool: 'write', step_line: '正在写 教案.docx' }),
      ev(7, 'tool.result', { tool: 'write', ok: true }),
      ev(8, 'tool.call', { tool: 'bash', step_line: '正在执行：python3 make_doc.py' }),
      ev(9, 'tool.result', { tool: 'bash', ok: false, user_message: '脚本报错了' }),
    ]);
    expect(lines).toEqual([
      '正在读 秋天的雨.docx',
      '正在写 教案.docx',
      '正在执行：python3 make_doc.py',
      '脚本报错了',
    ]);
  });

  it('keeps two different calls of the same tool apart', () => {
    const lines = processStepLines([
      ev(1, 'tool.call', { tool: 'read', step_line: '正在读 a.docx' }),
      ev(2, 'tool.call', { tool: 'read', step_line: '正在读 b.docx' }),
    ]);
    expect(lines).toEqual(['正在读 a.docx', '正在读 b.docx']);
  });

  it('is empty for a run with no steps yet', () => {
    expect(processStepLines([ev(1, 'run.status', { status: 'running' })])).toEqual([]);
  });
});
