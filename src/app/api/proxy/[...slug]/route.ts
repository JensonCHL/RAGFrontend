
import { getServerSession } from "next-auth/next"

import { authOptions } from "@/app/api/auth/[...nextauth]/route"

import { NextRequest, NextResponse } from "next/server"



const backendUrl = process.env.INTERNAL_API_URL



async function proxyRequest(req: NextRequest, slug: string[]) {

  const session = await getServerSession(authOptions)



  if (!session) {

    return new NextResponse(JSON.stringify({ error: "Unauthorized" }), {

      status: 401,

      headers: { "Content-Type": "application/json" },

    })

  }



  const path = slug.join("/")

  const apiUrl = `${backendUrl}/${path}`



  try {

    const backendResponse = await fetch(apiUrl, {

      method: req.method,

      headers: {

        ...req.headers,

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



export async function GET(req: NextRequest, { params }: { params: { slug: string[] } }) {

  return proxyRequest(req, params.slug)

}



export async function POST(req: NextRequest, { params }: { params: { slug: string[] } }) {

  return proxyRequest(req, params.slug)

}



export async function PUT(req: NextRequest, { params }: { params: { slug: string[] } }) {

  return proxyRequest(req, params.slug)

}



export async function DELETE(req: NextRequest, { params }: { params: { slug: string[] } }) {

  return proxyRequest(req, params.slug)

}


