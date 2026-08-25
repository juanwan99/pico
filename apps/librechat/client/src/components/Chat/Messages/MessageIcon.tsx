import { useMemo, memo } from 'react';
import { getEndpointField } from 'librechat-data-provider';
import type { Assistant, Agent } from 'librechat-data-provider';
import type { TMessageIcon } from '~/common';
import { useGetEndpointsQuery } from '~/data-provider';
import { getIconEndpoint } from '~/utils';
import WeiyujiMark from '~/components/Endpoints/WeiyujiMark';
import Icon from '~/components/Endpoints/Icon';

type MessageIconProps = {
  iconData?: TMessageIcon;
  assistant?: Assistant;
  agent?: Agent;
};

/**
 * Compares only the fields MessageIcon actually renders.
 * `agent.id` / `assistant.id` are intentionally omitted because
 * this component renders display properties only, not identity-derived content.
 */
export function arePropsEqual(prev: MessageIconProps, next: MessageIconProps): boolean {
  const checks: [unknown, unknown][] = [
    [prev.iconData?.endpoint, next.iconData?.endpoint],
    [prev.iconData?.model, next.iconData?.model],
    [prev.iconData?.iconURL, next.iconData?.iconURL],
    [prev.iconData?.modelLabel, next.iconData?.modelLabel],
    [prev.iconData?.isCreatedByUser, next.iconData?.isCreatedByUser],
    [prev.agent?.name, next.agent?.name],
    [prev.agent?.avatar?.filepath, next.agent?.avatar?.filepath],
    [prev.assistant?.name, next.assistant?.name],
    [prev.assistant?.metadata?.avatar, next.assistant?.metadata?.avatar],
  ];

  for (const [prevVal, nextVal] of checks) {
    if (prevVal !== nextVal) {
      return false;
    }
  }
  return true;
}

const MessageIcon = memo(({ iconData, assistant, agent }: MessageIconProps) => {
  const { data: endpointsConfig } = useGetEndpointsQuery();

  const agentName = agent?.name ?? '';
  const agentAvatar = agent?.avatar?.filepath ?? '';
  const assistantName = assistant?.name ?? '';
  const assistantAvatar = assistant?.metadata?.avatar ?? '';
  let avatarURL = '';
  if (assistant) {
    avatarURL = assistantAvatar;
  } else if (agent) {
    avatarURL = agentAvatar;
  }

  const iconURL = iconData?.iconURL;
  const endpoint = useMemo(
    () => getIconEndpoint({ endpointsConfig, iconURL, endpoint: iconData?.endpoint }),
    [endpointsConfig, iconURL, iconData?.endpoint],
  );

  const endpointIconURL = useMemo(
    () => getEndpointField(endpointsConfig, endpoint, 'iconURL'),
    [endpointsConfig, endpoint],
  );

  if (iconData?.isCreatedByUser === true) {
    return (
      <Icon
        isCreatedByUser
        endpoint={endpoint}
        iconURL={avatarURL || endpointIconURL}
        model={iconData?.model}
        assistantName={assistantName}
        agentName={agentName}
        size={28.8}
      />
    );
  }

  return (
    <div
      title="微与积"
      style={{ width: 28.8, height: 28.8 }}
      className="relative flex items-center justify-center overflow-hidden rounded-full bg-[#E8F4F8] p-0.5"
    >
      <WeiyujiMark size={28.8} />
    </div>
  );
}, arePropsEqual);

MessageIcon.displayName = 'MessageIcon';

export default MessageIcon;
