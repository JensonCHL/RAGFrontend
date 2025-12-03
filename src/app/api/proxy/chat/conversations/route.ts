// API Proxy for Chat Conversations
import { NextRequest, NextResponse } from "next/server";

const backendUrl = process.env.INTERNAL_API_URL || "http://localhost:5001";

export async function GET(req: NextRequest) {
  const { searchParams } = new URL(req.url);
  const user_id = searchParams.get("user_id");

  if (!user_id) {
    return NextResponse.json({ error: "user_id is required" }, { status: 400 });
  }

  try {
    const response = await fetch(
      `${backendUrl}/api/chat/conversations?user_id=${user_id}`
    );

    if (!response.ok) {
      throw new Error(`Backend error: ${response.status}`);
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error("Error fetching conversations:", error);
    return NextResponse.json(
      { error: "Failed to fetch conversations" },
      { status: 500 }
    );
  }
}

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const { user_id, title } = body;

    if (!user_id || !title) {
      return NextResponse.json(
        { error: "user_id and title are required" },
        { status: 400 }
      );
    }

    const response = await fetch(`${backendUrl}/api/chat/conversations`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ user_id, title }),
    });

    if (!response.ok) {
      throw new Error(`Backend error: ${response.status}`);
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error("Error creating conversation:", error);
    return NextResponse.json(
      { error: "Failed to create conversation" },
      { status: 500 }
    );
  }
}
