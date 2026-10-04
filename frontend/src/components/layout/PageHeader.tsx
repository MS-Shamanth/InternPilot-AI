interface PageHeaderProps {
  title: string;
  description?: string;
}

/** The page's single `h1` plus a short description. */
export function PageHeader({ title, description }: PageHeaderProps) {
  return (
    <header className="mb-6">
      <h1 className="text-2xl font-semibold text-ink-900">{title}</h1>
      {description !== undefined && <p className="mt-1 text-sm text-ink-600">{description}</p>}
    </header>
  );
}
