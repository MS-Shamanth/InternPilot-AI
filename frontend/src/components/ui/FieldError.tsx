interface FieldErrorProps {
  id: string;
  message: string;
}

/** Inline validation message; the "Error:" prefix keeps it from relying on color alone. */
export function FieldError({ id, message }: FieldErrorProps) {
  return (
    <p id={id} className="mt-1 text-xs font-medium text-danger-700">
      <span className="font-semibold">Error:</span> {message}
    </p>
  );
}
