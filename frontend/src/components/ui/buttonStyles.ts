import { cx } from '../../lib/classNames';

export type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'danger';
export type ButtonSize = 'sm' | 'md';

const BASE =
  'inline-flex shrink-0 items-center justify-center rounded font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-60';

const VARIANT_CLASSES: Record<ButtonVariant, string> = {
  primary: 'bg-pilot-700 text-white hover:bg-pilot-800 disabled:hover:bg-pilot-700',
  secondary: 'border border-ink-300 bg-white text-ink-800 hover:bg-ink-100 disabled:hover:bg-white',
  ghost: 'text-ink-700 hover:bg-ink-100 hover:text-ink-900 disabled:hover:bg-transparent',
  danger: 'bg-danger-700 text-white hover:bg-danger-800 disabled:hover:bg-danger-700',
};

const SIZE_CLASSES: Record<ButtonSize, string> = {
  sm: 'h-8 gap-1.5 px-3 text-sm',
  md: 'h-10 gap-2 px-4 text-sm',
};

const ICON_SIZE_CLASSES: Record<ButtonSize, string> = {
  sm: 'h-8 w-8 text-base',
  md: 'h-10 w-10 text-lg',
};

interface ButtonClassOptions {
  variant?: ButtonVariant;
  size?: ButtonSize;
  iconOnly?: boolean;
  className?: string;
}

/**
 * Classes for anything that should look like a button, including router `Link`s.
 * Focus styling comes from the global `:focus-visible` rule in `src/index.css`.
 */
export function buttonClasses({
  variant = 'primary',
  size = 'md',
  iconOnly = false,
  className,
}: ButtonClassOptions = {}): string {
  return cx(
    BASE,
    VARIANT_CLASSES[variant],
    iconOnly ? ICON_SIZE_CLASSES[size] : SIZE_CLASSES[size],
    className,
  );
}
