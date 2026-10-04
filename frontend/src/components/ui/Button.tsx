import { forwardRef } from 'react';
import type { ButtonHTMLAttributes } from 'react';

import { buttonClasses } from './buttonStyles';
import type { ButtonSize, ButtonVariant } from './buttonStyles';
import { Spinner } from './Spinner';

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  /** Disables the button, sets `aria-busy` and shows a spinner with screen-reader text. */
  isLoading?: boolean;
}

/** Native `<button>` with the kit's variants; `type` defaults to `"button"`. */
export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  {
    variant = 'primary',
    size = 'md',
    isLoading = false,
    disabled = false,
    type = 'button',
    className,
    children,
    ...rest
  },
  ref,
) {
  return (
    <button
      ref={ref}
      type={type}
      disabled={disabled || isLoading}
      aria-busy={isLoading || undefined}
      className={buttonClasses({ variant, size, className })}
      {...rest}
    >
      {isLoading && <Spinner />}
      {children}
      {isLoading && <span className="sr-only"> (loading)</span>}
    </button>
  );
});
