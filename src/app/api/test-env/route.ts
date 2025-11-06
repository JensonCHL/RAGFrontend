import { NextResponse } from 'next/server';

export async function GET() {
  // Log to server console
  console.log('APP_USERNAME from process.env:', process.env.APP_USERNAME);
  console.log('APP_PASSWORD from process.env:', process.env.APP_PASSWORD ? '[REDACTED]' : 'undefined');
  
  return NextResponse.json({
    appUsernameExists: !!process.env.APP_USERNAME,
    appPasswordExists: !!process.env.APP_PASSWORD,
    appUsername: process.env.APP_USERNAME,
    appPasswordLength: process.env.APP_PASSWORD ? process.env.APP_PASSWORD.length : 0,
    nextAuthSecretExists: !!process.env.NEXTAUTH_SECRET,
  });
}