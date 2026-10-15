import type { Metadata } from "next";
import { LoginForm } from "./LoginForm";

export const metadata: Metadata = {
  title: "Sign in · Aroma AI",
};

export default function LoginPage() {
  return <LoginForm />;
}
