type FormFieldProps = {
  id: string;
  label: string;
  type?: string;
  autoComplete?: string;
  value: string;
  error?: string;
  hint?: string;
  autoCapitalize?: string;
  spellCheck?: boolean;
  onChange: (value: string) => void;
};

export function FormField({
  id,
  label,
  type = "text",
  autoComplete,
  value,
  error,
  hint,
  autoCapitalize,
  spellCheck,
  onChange,
}: FormFieldProps) {
  const describedBy = [hint && `${id}-hint`, error && `${id}-error`].filter(Boolean).join(" ");
  return (
    <div className="flex flex-col gap-1">
      <label htmlFor={id} className="font-medium">
        {label}
      </label>
      <input
        id={id}
        name={id}
        type={type}
        autoComplete={autoComplete}
        autoCapitalize={autoCapitalize}
        spellCheck={spellCheck}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        aria-invalid={error ? true : undefined}
        aria-describedby={describedBy || undefined}
        className="rounded-md border border-zinc-400 px-3 py-2 dark:border-zinc-600 dark:bg-zinc-900"
      />
      {hint && (
        <p id={`${id}-hint`} className="text-sm text-zinc-600 dark:text-zinc-400">
          {hint}
        </p>
      )}
      {error && (
        <p id={`${id}-error`} className="text-sm text-red-700 dark:text-red-400">
          {error}
        </p>
      )}
    </div>
  );
}
