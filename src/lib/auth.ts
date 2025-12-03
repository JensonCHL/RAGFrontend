import { AuthOptions } from "next-auth";
import CredentialsProvider from "next-auth/providers/credentials";

export const authOptions: AuthOptions = {
  providers: [
    CredentialsProvider({
      name: "Credentials",
      credentials: {
        username: { label: "Username", type: "text", placeholder: "username" },
        password: { label: "Password", type: "password" },
      },
      async authorize(credentials) {
        // 1. Check Admin Credentials from .env (Multiple Admins Supported)
        const admins = [];

        // Primary Admin
        const adminUsername = process.env.APP_USERNAME || "admin";
        admins.push({
          username: adminUsername,
          password: process.env.APP_PASSWORD,
          name: adminUsername.includes("@")
            ? adminUsername.split("@")[0]
            : "Admin User",
          email: adminUsername.includes("@")
            ? adminUsername
            : "admin@example.com",
          role: "admin",
        });

        // Additional Admins from .env
        let i = 1;
        while (
          process.env[`APP_USERNAME${i}`] &&
          process.env[`APP_PASSWORD${i}`]
        ) {
          const username = process.env[`APP_USERNAME${i}`] || `user${i}`;
          admins.push({
            username: username,
            password: process.env[`APP_PASSWORD${i}`],
            name: username.includes("@")
              ? username.split("@")[0]
              : `Admin ${i}`,
            email: username.includes("@") ? username : `admin${i}@example.com`,
            role: "admin",
          });
          i++;
        }

        // Check against Admin list
        const validAdmin = admins.find(
          (user) =>
            credentials?.username === user.username &&
            credentials?.password === user.password
        );

        if (validAdmin) {
          return {
            id: `admin-${validAdmin.username}`,
            name: validAdmin.name,
            email: validAdmin.email,
            username: validAdmin.username,
            role: validAdmin.role,
          };
        }

        // 2. Check Database Users via Backend API (Regular Users)
        try {
          const backendUrl =
            process.env.INTERNAL_API_URL || "http://localhost:5001";
          const res = await fetch(`${backendUrl}/api/chat/auth/verify`, {
            method: "POST",
            body: JSON.stringify({
              username: credentials?.username,
              password: credentials?.password,
            }),
            headers: { "Content-Type": "application/json" },
          });

          if (res.ok) {
            const user = await res.json();
            return {
              id: user.id,
              name: user.username,
              email: user.email,
              username: user.username,
              role: user.role, // Should be 'user' from DB
            };
          }
        } catch (error) {
          console.error("Auth verification failed:", error);
        }

        return null;
      },
    }),
  ],
  callbacks: {
    async jwt({ token, user }: { token: any; user: any }) {
      if (user) {
        token.id = user.id;
        token.username = user.username;
        token.email = user.email;
        token.name = user.name;
        token.role = user.role;
      }
      return token;
    },
    async session({ session, token }: { session: any; token: any }) {
      if (session.user) {
        session.user.id = token.id as string;
        session.user.username = token.username as string;
        session.user.email = token.email as string;
        session.user.name = token.name as string;
        session.user.role = token.role as string;
      }
      return session;
    },
  },
  pages: {
    signIn: "/login",
  },
  session: {
    strategy: "jwt",
    maxAge: 24 * 60 * 60, // 24 hours
  },
  cookies: {
    sessionToken: {
      name: `next-auth.session-token`,
      options: {
        httpOnly: true,
        sameSite: "lax",
        path: "/",
        secure: false,
      },
    },
    callbackUrl: {
      name: `next-auth.callback-url`,
      options: {
        sameSite: "lax",
        path: "/",
        secure: false,
      },
    },
    csrfToken: {
      name: `next-auth.csrf-token`,
      options: {
        httpOnly: true,
        sameSite: "lax",
        path: "/",
        secure: false,
      },
    },
  },
  secret: process.env.NEXTAUTH_SECRET,
};
