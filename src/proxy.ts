import { withAuth } from "next-auth/middleware"

export default withAuth({
  pages: {
    signIn: "/login",
  },
})

export const config = {
  matcher: [
    /*
     * Match all request paths except for the ones starting with:
     * - api (API routes)
     * - _next/static (static files)
     * - _next/image (image optimization files)
     * - favicon.ico (favicon file)
     * - login (login page)
     * - .*.png (PNG images)
     * - .*.jpg (JPG images)
     * - .*.jpeg (JPEG images)
     * - .*.gif (GIF images)
     * - .*.svg (SVG images)
     */
    '/((?!api|_next/static|_next/image|favicon.ico|login|.*\\.png|.*\\.jpg|.*\\.jpeg|.*\\.gif|.*\\.svg).*)',
  ],
}