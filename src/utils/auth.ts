import { getServerSession } from "next-auth";
import { authOptions } from "@/lib/auth";

export async function isAuthenticated() {
  const session = await getServerSession(authOptions);
  return !!session;
}

export async function getCurrentUser() {
  const session = await getServerSession(authOptions);
  return session?.user || null;
}