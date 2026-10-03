import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import PicoThinkingChain, {
  isMostlyChinese,
} from '../../components/Chat/Messages/PicoThinkingChain';
import { PicoRunStepsContext, type PicoRunSteps } from '../../hooks/Pico/PicoRunStepsContext';

function withSteps(ui: React.ReactElement, steps: PicoRunSteps) {
  return <PicoRunStepsContext.Provider value={steps}>{ui}</PicoRunStepsContext.Provider>;
}

const STEPS = ['正在读 秋天的雨.docx', '正在检索：教学重难点', '正在写 教案.docx', '正在执行：python3 make_doc.py', '正在核对文档'];

describe('PicoThinkingChain', () => {
  it('shows a live placeholder in a 4-line box while submitting with nothing yet', () => {
    render(<PicoThinkingChain isSubmitting />);
    expect(screen.getByTestId('pico-thinking-chain')).toHaveTextContent('正在思考…');
    expect(screen.getByTestId('pico-thinking-chain')).toHaveAttribute('data-submitting', 'true');
    const body = screen.getByTestId('pico-thinking-chain-body');
    expect(body.className).toMatch(/\bh-20\b/);
    expect(body.className).toMatch(/justify-end/);
    expect(body.className).toMatch(/overflow-hidden/);
  });

  it('rolls the run steps in the box, newest last', () => {
    render(
      withSteps(<PicoThinkingChain isSubmitting withRunSteps />, { active: true, lines: STEPS }),
    );
    const body = screen.getByTestId('pico-thinking-chain-body');
    expect(screen.getByTestId('pico-thinking-chain')).toHaveTextContent('正在处理');
    expect(body.lastChild).toHaveTextContent('▸ 正在核对文档');
    expect(body.firstChild).toHaveTextContent('▸ 正在读 秋天的雨.docx');
  });

  it('ignores the previous run while the new one has not started', () => {
    render(
      withSteps(<PicoThinkingChain isSubmitting withRunSteps />, { active: false, lines: STEPS }),
    );
    expect(screen.getByTestId('pico-thinking-chain')).toHaveTextContent('正在思考…');
    expect(screen.queryByText(/秋天的雨/)).toBeNull();
  });

  it('keeps English thinking off the screen, shows Chinese thinking', () => {
    const { rerender } = render(
      <PicoThinkingChain isSubmitting text="**Developing Lesson Plan** I'm refining the hook" />,
    );
    expect(screen.queryByText(/Developing/)).toBeNull();
    rerender(<PicoThinkingChain isSubmitting text="先看附件里的课文，再定重难点。" />);
    expect(screen.getByTestId('pico-thinking-chain-body')).toHaveTextContent('先看附件里的课文');
  });

  it('folds into 处理过程 after the run and expands on click', () => {
    render(withSteps(<PicoThinkingChain withRunSteps />, { active: false, lines: STEPS }));
    const chain = screen.getByTestId('pico-thinking-chain');
    expect(chain).toHaveTextContent('处理过程 · 5 步 · 展开');
    expect(screen.queryByTestId('pico-thinking-chain-body')).toBeNull();
    fireEvent.click(chain);
    expect(chain).toHaveAttribute('data-expanded', 'true');
    expect(screen.getByTestId('pico-thinking-chain-body')).toHaveTextContent('▸ 正在写 教案.docx');
  });

  it('renders nothing when idle and empty, or for an older reply', () => {
    const { container, rerender } = render(<PicoThinkingChain />);
    expect(container).toBeEmptyDOMElement();
    rerender(withSteps(<PicoThinkingChain />, { active: false, lines: STEPS }));
    expect(container).toBeEmptyDOMElement();
  });

  it('isMostlyChinese', () => {
    expect(isMostlyChinese('先看附件')).toBe(true);
    expect(isMostlyChinese('Refining the 《秋天的雨》 lesson plan for grade three')).toBe(false);
    expect(isMostlyChinese('')).toBe(false);
  });
});
