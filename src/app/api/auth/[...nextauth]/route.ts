import NextAuth from "next-auth"
import CredentialsProvider from "next-auth/providers/credentials"
import { AuthOptions } from "next-auth"

export const authOptions: AuthOptions = {
  providers: [
    CredentialsProvider({
      name: "Credentials",
      credentials: {
        username: { label: "Username", type: "text", placeholder: "username" },
        password: { label: "Password", type: "password" }
      },
      async authorize(credentials) {
        // Support for multiple users
        const users = [
          {
            username: process.env.APP_USERNAME,
            password: process.env.APP_PASSWORD,
            name: "Admin User",
            email: "admin@example.com"
          }
        ];
        
        // Add additional users from environment variables
        let i = 1;
        while (process.env[`APP_USERNAME${i}`] && process.env[`APP_PASSWORD${i}`]) {
          users.push({
            username: process.env[`APP_USERNAME${i}`],
            password: process.env[`APP_PASSWORD${i}`],
            name: `User ${i}`,
            email: `user${i}@example.com`
          });
          i++;
        }
        
        // Check if credentials match any user
        const validUser = users.find(
          user => credentials?.username === user.username && credentials?.password === user.password
        );
        
        if (validUser) {
          return {
            id: users.indexOf(validUser).toString(),
            name: validUser.name,
            email: validUser.email,
            username: validUser.username
          } as any
        }
        
        return null
      }
    })
  ],
  callbacks: {
    async jwt({ token, user }: { token: any; user: any }) {
      if (user) {
        token.id = user.id
        token.username = user.username
      }
      return token
    },
    async session({ session, token }: { session: any; token: any }) {
      if (session.user) {
        session.user.id = token.id as string
        session.user.username = token.username as string
      }
      return session
    }
  },
  pages: {
    signIn: "/login",
  },
  session: {
    strategy: "jwt",
  },
  secret: process.env.NEXTAUTH_SECRET,
}

const handler = NextAuth(authOptions)

export { handler as GET, handler as POST }