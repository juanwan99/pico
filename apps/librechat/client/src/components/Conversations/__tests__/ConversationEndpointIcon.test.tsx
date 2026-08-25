import React from 'react';
import { render, screen } from '@testing-library/react';
import { EModelEndpoint } from 'librechat-data-provider';
import type { TConversation } from 'librechat-data-provider';
import ConversationEndpointIcon from '../ConversationEndpointIcon';

const convo = {
  conversationId: 'c1',
  endpoint: EModelEndpoint.openAI,
  iconURL: '/assets/openai.svg',
  title: 'New Chat',
} as TConversation;

describe('ConversationEndpointIcon', () => {
  it('renders the 微与积 mark even when the convo carries an OpenAI/Codex icon URL', () => {
    render(<ConversationEndpointIcon conversation={convo} size={20} />);
    const mark = screen.getByAltText('微与积');
    expect(mark).toHaveAttribute('src', '/assets/weiyuji-mark.svg');
  });
});
