import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { z } from "zod";
import { ApiError, apiFetch } from "./api";

// Mirrors backend/app/schemas/auth.py.
export const MIN_PASSWORD_LENGTH = 10;
export const MAX_PASSWORD_BYTES = 72;

export const membershipSchema = z.object({
  company_id: z.string(),
  company_display_name: z.string(),
  company_review_status: z.enum(["PENDING_REVIEW", "APPROVED", "REJECTED", "SUSPENDED"]),
  role: z.enum(["OWNER", "REPRESENTATIVE"]),
});

export const userSchema = z.object({
  user_id: z.string(),
  email: z.string(),
  display_name: z.string(),
  is_admin: z.boolean(),
  membership: membershipSchema.nullable(),
});

export type User = z.infer<typeof userSchema>;

export const loginFormSchema = z.object({
  email: z.string().trim().min(1, "Enter your email"),
  password: z.string().min(1, "Enter your password"),
});

export const registerFormSchema = z.object({
  displayName: z.string().trim().min(1, "Enter your name").max(100, "Name is too long"),
  email: z.email("Enter a valid email address"),
  password: z
    .string()
    .min(MIN_PASSWORD_LENGTH, `Use at least ${MIN_PASSWORD_LENGTH} characters`)
    .refine(
      (value) => new TextEncoder().encode(value).length <= MAX_PASSWORD_BYTES,
      "Password is too long",
    ),
});

export type LoginForm = z.infer<typeof loginFormSchema>;
export type RegisterForm = z.infer<typeof registerFormSchema>;

export const currentUserKey = ["auth", "me"] as const;

/** The signed-in user, or null when signed out. */
export function useCurrentUser() {
  return useQuery({
    queryKey: currentUserKey,
    queryFn: async (): Promise<User | null> => {
      try {
        return await apiFetch("/api/auth/me", userSchema);
      } catch (error) {
        if (error instanceof ApiError && error.status === 401) return null;
        throw error;
      }
    },
    retry: false,
    staleTime: 60_000,
  });
}

export function useLogin() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (form: LoginForm) =>
      apiFetch("/api/auth/login", userSchema, { method: "POST", body: form }),
    onSuccess: (user) => queryClient.setQueryData(currentUserKey, user),
  });
}

export function useRegister() {
  const queryClient = useQueryClient();
  return useMutation({
    // Only these three fields are sent; the server ignores anything else anyway.
    mutationFn: (form: RegisterForm) =>
      apiFetch("/api/auth/register", userSchema, {
        method: "POST",
        body: { email: form.email, password: form.password, display_name: form.displayName },
      }),
    onSuccess: (user) => queryClient.setQueryData(currentUserKey, user),
  });
}

export function useLogout() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => apiFetch("/api/auth/logout", null, { method: "POST" }),
    onSuccess: () => queryClient.setQueryData(currentUserKey, null),
  });
}

/** Field errors from a failed zod parse, keyed by field name. */
export function fieldErrors(error: z.ZodError): Record<string, string> {
  const errors: Record<string, string> = {};
  for (const issue of error.issues) {
    const key = String(issue.path[0]);
    errors[key] ??= issue.message;
  }
  return errors;
}
