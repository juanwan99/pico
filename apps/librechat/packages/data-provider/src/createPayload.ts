import type * as t from './types';
import { EndpointURLs } from './config';
import * as s from './schemas';

/** Resolves the browser's IANA timezone so the server can localize prompt variables. */
function getUserTimezone(): string | undefined {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || undefined;
  } catch {
    return undefined;
  }
}

function picoSkillMarker(manualSkills?: string[]): string {
  const first = manualSkills?.find((skill) => typeof skill === 'string' && skill.trim());
  if (!first) {
    return '';
  }
  const normalized = first.trim().toLowerCase().replace(/_/g, '-');
  const aliases: Record<string, string> = {
    'skill.chat': 'skill-chat',
    'skill-chat': 'skill-chat',
    'skill.read': 'skill-read',
    'skill-read': 'skill-read',
    'skill.write-s7': 'skill-write-s7',
    'skill.write_s7': 'skill-write-s7',
    'skill-write-s7': 'skill-write-s7',
  };
  const id = aliases[first.trim().toLowerCase()] ?? aliases[normalized];
  return id ? `【Pico-Skill:${id}】\n` : '';
}

export default function createPayload(submission: t.TSubmission) {
  const {
    isEdited,
    addedConvo,
    userMessage,
    isContinued,
    isTemporary,
    isRegenerate,
    conversation,
    editedContent,
    ephemeralAgent,
    endpointOption,
    manualSkills,
    clientRequestId,
  } = submission;
  const { conversationId } = s.tConvoUpdateSchema.parse(conversation);
  const { endpoint: _e, endpointType } = endpointOption as {
    endpoint: s.EModelEndpoint;
    endpointType?: s.EModelEndpoint;
  };

  const endpoint = _e as s.EModelEndpoint;
  let server = `${EndpointURLs[s.EModelEndpoint.agents]}/${endpoint}`;
  if (s.isAssistantsEndpoint(endpoint)) {
    server =
      EndpointURLs[(endpointType ?? endpoint) as 'assistants' | 'azureAssistants'] +
      (isEdited ? '/modify' : '');
  }

  const payload: t.TPayload = {
    ...userMessage,
    ...endpointOption,
    endpoint,
    addedConvo,
    isTemporary,
    isRegenerate,
    editedContent,
    conversationId,
    isContinued: !!(isEdited && isContinued),
    ephemeralAgent: s.isAssistantsEndpoint(endpoint) ? undefined : ephemeralAgent,
    manualSkills: s.isAssistantsEndpoint(endpoint) ? undefined : manualSkills,
    timezone: getUserTimezone(),
    clientRequestId,
  };
  const marker = picoSkillMarker(manualSkills);
  if (marker && typeof payload.text === 'string' && !payload.text.includes('【Pico-Skill:')) {
    payload.text = `${marker}${payload.text}`;
  }

  return { server, payload };
}
