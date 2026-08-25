import { memo } from 'react';
import type { TConversation } from 'librechat-data-provider';
import WeiyujiMark from '~/components/Endpoints/WeiyujiMark';
import { cn } from '~/utils';

type EndpointIconContext = 'message' | 'nav' | 'landing' | 'menu-item';

type ConversationEndpointIconProps = {
  conversation: TConversation;
  className?: string;
  context?: EndpointIconContext;
  size?: number;
};

/** Left session list always uses the 微与积 mark, never Codex/OpenAI. */
function ConversationEndpointIcon({
  className,
  size = 20,
}: ConversationEndpointIconProps) {
  return (
    <div
      title="微与积"
      style={{ width: size, height: size }}
      className={cn(
        'relative flex shrink-0 items-center justify-center overflow-hidden rounded-full bg-[#E8F4F8] p-0.5',
        className,
      )}
    >
      <WeiyujiMark size={size} />
    </div>
  );
}

export default memo(ConversationEndpointIcon, (prevProps, nextProps) => {
  return prevProps.className === nextProps.className && prevProps.size === nextProps.size;
});
