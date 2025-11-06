import { NextResponse } from 'next/server';

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const username = searchParams.get('username');
  const password = searchParams.get('password');
  
  // Use credentials from environment variables
  const validUsername = process.env.APP_USERNAME;
  const validPassword = process.env.APP_PASSWORD;
  
  const usernameMatch = username === validUsername;
  const passwordMatch = password === validPassword;
  const authSuccess = usernameMatch && passwordMatch;
  
  return NextResponse.json({
    providedUsername: username,
    providedPasswordLength: password ? password.length : 0,
    expectedUsername: validUsername,
    expectedPasswordLength: validPassword ? validPassword.length : 0,
    usernameMatch,
    passwordMatch,
    authSuccess,
  });
}