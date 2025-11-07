
import { getServerSession } from "next-auth/next"
import { authOptions } from "@/app/api/auth/[...nextauth]/route"
import { NextRequest, NextResponse } from "next/server"

const backendUrl = process.env.INTERNAL_API_URL

export async function handler(req: NextRequest) {
  const session = await getServerSession(authOptions)

  if (!session) {
    return new NextResponse(JSON.stringify({ error: "Unauthorized" }), {
      status: 401,
      headers: { "Content-Type": "application/json" },
    })
  }

  const { slug } = req.nextUrl
  const apiUrl = `${backendUrl}/${slug}`

  try {
    const backendResponse = await fetch(apiUrl, {
      method: req.method,
      headers: {
        ...req.headers,
        // Add any custom headers here if needed
      },
      body: req.body,
      // @ts-ignore
      duplex: "half",
    })

    return new NextResponse(backendResponse.body, {
      status: backendResponse.status,
      statusText: backendResponse.statusText,
      headers: backendResponse.headers,
    })
  } catch (error) {
    console.error("Proxy error:", error)
    return new NextResponse(JSON.stringify({ error: "Proxy error" }), {
      status: 500,
      headers: { "Content-Type": "application/json" },
    })
  }
}

export { handler as GET, handler as POST, handler as PUT, handler as DELETE }
