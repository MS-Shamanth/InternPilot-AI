import { forwardRef } from 'react';
import type { ButtonHTMLAttributes, ReactNode } from 'react';

import { buttonClasses } from './buttonStyles';
import type { ButtonSize, ButtonVariant } from './buttonStyles';

export interface IconButtonProps extends Omit<
  ButtonHTMLAttributes<HTMLButtonElement>,
  'children' | 'aria-label'
> {
  /** Required: an icon-only button has no visible text to name it. */
  'aria-label': string;
  /** Decorative glyph or SVG; it is hidden from assistive technology. */
  icon: ReactNode;
  variant?: ButtonVariant;
  size?: ButtonSize;
}

/** Square icon-only button whose accessible name comes from `aria-label`. */
export const IconButton = forwardRef<HTMLButtonElement, IconButtonProps>(function IconButton(
  { icon, variant = 'ghost', size = 'md', type = 'button', className, ...rest },
  ref,
) {
  return (
    <button
      ref={ref}
      type={type}
      className={buttonClasses({ variant, size, iconOnly: true, className })}
      {...rest}
    >
      <span aria-hidden="true">{icon}</span>
    </button>
  );
});
