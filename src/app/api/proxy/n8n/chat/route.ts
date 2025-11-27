// Next.js API Proxy Route for n8n Chat
import { getServerSession } from "next-auth/next";
import { authOptions } from "@/lib/auth";
import { NextRequest } from "next/server";

const backendUrl = process.env.INTERNAL_API_URL || "http://localhost:5001";

export async function POST(req: NextRequest) {
  const session = await getServerSession(authOptions);

  // Check authentication
  if (!session) {
    return new Response(JSON.stringify({ error: "Unauthorized" }), {
      status: 401,
      headers: { "Content-Type": "application/json" },
    });
  }

  try {
    const body = await req.json();

    console.log("Forwarding chat request to FastAPI backend");

    // Forward to FastAPI backend
    const response = await fetch(`${backendUrl}/api/chat/send`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        ...body,
        user_id: session.user?.email || session.user?.name || "unknown",
      }),
    });

    if (!response.ok) {
      const errorText = await response.text();
      console.error("FastAPI error:", errorText);
      return new Response(
        JSON.stringify({ error: `Backend error: ${response.status}` }),
        { status: 500, headers: { "Content-Type": "application/json" } }
      );
    }

    // Forward the streaming response
    return new Response(response.body, {
      status: 200,
      headers: {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache",
        Connection: "keep-alive",
      },
    });
  } catch (error) {
    const errMsg = error instanceof Error ? error.message : String(error);
    console.error("Proxy error:", errMsg);
    return new Response(
      JSON.stringify({
        error: "Failed to process chat request",
        details: errMsg,
      }),
      { status: 500, headers: { "Content-Type": "application/json" } }
    );
  }
}
