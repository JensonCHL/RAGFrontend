import { NextRequest, NextResponse } from "next/server";

const backendUrl = process.env.INTERNAL_API_URL || "http://localhost:5001";

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();

    const response = await fetch(`${backendUrl}/api/chat/auth/verify`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });

    if (!response.ok) {
      return NextResponse.json(
        { error: "Invalid credentials" },
        { status: response.status }
      );
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error("Error verifying user:", error);
    return NextResponse.json({ error: "Verification failed" }, { status: 500 });
  }
}
