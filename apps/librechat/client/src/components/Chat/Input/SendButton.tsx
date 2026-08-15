import React, { forwardRef } from 'react';
import { useWatch } from 'react-hook-form';
import type { Control } from 'react-hook-form';
import { TooltipAnchor } from '@librechat/client';
import { PicoIcon } from '~/components/ui/pico-icons';
import { useLocalize } from '~/hooks';
import { cn } from '~/utils';

type SendButtonProps = {
  disabled: boolean;
  control: Control<{ text: string }>;
};

const SubmitButton = React.memo(
  forwardRef((props: { disabled: boolean }, ref: React.ForwardedRef<HTMLButtonElement>) => {
    const localize = useLocalize();
    return (
      <TooltipAnchor
        description={localize('com_nav_send_message')}
        render={
          <button
            ref={ref}
            aria-label={localize('com_nav_send_message')}
            id="send-button"
            disabled={props.disabled}
            className={cn(
              'inline-flex h-8 w-8 items-center justify-center rounded-md text-[color:var(--pico-ink)] outline-offset-4 transition-colors hover:bg-black/[0.04] disabled:cursor-not-allowed disabled:text-[color:var(--pico-ink-3)] disabled:opacity-40',
            )}
            data-testid="send-button"
            type="submit"
          >
            <PicoIcon name="arrow-up" />
          </button>
        }
      />
    );
  }),
);

const SendButton = React.memo(
  forwardRef((props: SendButtonProps, ref: React.ForwardedRef<HTMLButtonElement>) => {
    const data = useWatch({ control: props.control });
    const content = data?.text?.trim();
    return <SubmitButton ref={ref} disabled={props.disabled || !content} />;
  }),
);

export default SendButton;
