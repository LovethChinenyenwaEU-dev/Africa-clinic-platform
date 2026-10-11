import { z } from "zod";

// What the person types on the login screen. This gives friendly messages only:
// the backend remains the real check.
export const loginFormSchema = z.object({
  email: z.string().trim().min(1, "Enter your email.").max(254, "That email is too long."),
  password: z.string().min(1, "Enter your password.").max(128, "That password is too long."),
});
export type LoginForm = z.infer<typeof loginFormSchema>;

// What the backend answers to POST /auth/login.
export const tokenResponseSchema = z.object({
  access_token: z.string().min(1),
  token_type: z.literal("bearer"),
});
export type TokenResponse = z.infer<typeof tokenResponseSchema>;

// The roles the backend knows. If it ever sends a new one, parsing fails loudly
// and we update this list on purpose, rather than the screen guessing.
export const roleSchema = z.enum(["admin", "front_desk", "nurse", "doctor", "billing"]);
export type Role = z.infer<typeof roleSchema>;

// What the backend answers to GET /auth/me. No password hash ever appears here.
export const meSchema = z.object({
  id: z.string().uuid(),
  tenant_id: z.string().uuid(),
  email: z.string(),
  full_name: z.string(),
  role: roleSchema,
});
export type Me = z.infer<typeof meSchema>;