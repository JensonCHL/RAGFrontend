import { getServerSession } from "next-auth/next"
import { authOptions } from "@/lib/auth"
import { NextRequest, NextResponse } from "next/server"

const backendUrl = process.env.INTERNAL_API_URL

async function proxyRequest(req: NextRequest, slug: string[]) {
  const session = await getServerSession(authOptions)

  // Log request for debugging
  console.log("Proxy request:", {
    method: req.method,
    url: req.url,
    path: slug?.join("/"),
    hasSession: !!session,
    backendUrl: backendUrl
  });

  if (!session) {
    return new NextResponse(JSON.stringify({ error: "Unauthorized" }), {
      status: 401,
      headers: { "Content-Type": "application/json" },
    })
  }

  const path = (slug || []).join("/")
  const apiUrl = `${backendUrl}/${path}`

  try {
    const headers = new Headers(req.headers);
    // Ensure Content-Type is explicitly forwarded if present
    if (req.headers.get('content-type')) {
      headers.set('content-type', req.headers.get('content-type') as string);
    }

    // Remove headers that might cause issues
    headers.delete('host');
    headers.delete('connection');

    console.log("Forwarding request to:", apiUrl);

    const backendResponse = await fetch(apiUrl, {
      method: req.method,
      headers: headers,
      body: req.body,
      // @ts-ignore
      duplex: "half",
    })

    console.log("Backend response:", {
      status: backendResponse.status,
      statusText: backendResponse.statusText,
      headers: Object.fromEntries(backendResponse.headers.entries())
    });

    // Clone the response to read the body for debugging
    const responseBody = await backendResponse.clone().text();
    console.log("Response body:", responseBody.substring(0, 500) + (responseBody.length > 500 ? "..." : ""));

    // Forward all headers except problematic ones
    const responseHeaders = new Headers(backendResponse.headers);
    responseHeaders.delete('transfer-encoding');
    responseHeaders.delete('connection');

    return new NextResponse(backendResponse.body, {
      status: backendResponse.status,
      statusText: backendResponse.statusText,
      headers: responseHeaders,
    })
  } catch (error) {
    console.error("Proxy error:", error)
    return new NextResponse(JSON.stringify({ error: "Proxy error", details: error.message }), {
      status: 500,
      headers: { "Content-Type": "application/json" },
    })
  }
}

// Each route handler must `await` params in Next.js 14+
export async function GET(req: NextRequest, context: { params: Promise<{ slug?: string[] }> }) {
  const { slug } = await context.params
  return proxyRequest(req, slug || [])
}

export async function POST(req: NextRequest, context: { params: Promise<{ slug?: string[] }> }) {
  const { slug } = await context.params
  return proxyRequest(req, slug || [])
}

export async function PUT(req: NextRequest, context: { params: Promise<{ slug?: string[] }> }) {
  const { slug } = await context.params
  return proxyRequest(req, slug || [])
}

export async function DELETE(req: NextRequest, context: { params: Promise<{ slug?: string[] }> }) {
  const { slug } = await context.params
  return proxyRequest(req, slug || [])
}
