// API Proxy for Saving Messages
import { NextRequest, NextResponse } from "next/server";

const backendUrl = process.env.INTERNAL_API_URL || "http://localhost:5001";

export async function POST(
  req: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const body = await req.json();
    const { user_id, role, content, sources, metadata } = body;
    const { id: conversationId } = await params;

    if (!user_id || !role || !content) {
      return NextResponse.json(
        { error: "user_id, role, and content are required" },
        { status: 400 }
      );
    }

    const response = await fetch(
      `${backendUrl}/api/chat/conversations/${conversationId}/messages`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_id, role, content, sources, metadata }),
      }
    );

    if (!response.ok) {
      throw new Error(`Backend error: ${response.status}`);
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error("Error saving message:", error);
    return NextResponse.json(
      { error: "Failed to save message" },
      { status: 500 }
    );
  }
}
