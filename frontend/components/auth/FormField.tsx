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
        className="min-h-[46px] rounded-[10px] border border-line-input bg-white px-3 text-base text-ink"
      />
      {hint && (
        <p id={`${id}-hint`} className="text-sm text-text-subtle">
          {hint}
        </p>
      )}
      {error && (
        <p id={`${id}-error`} className="text-sm font-semibold text-bad">
          {error}
        </p>
      )}
    </div>
  );
}
