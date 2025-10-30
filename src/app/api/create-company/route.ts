import { NextRequest, NextResponse } from 'next/server';
import fs from 'fs-extra';
import path from 'path';

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    let { companyName } = body;
    
    if (!companyName) {
      return NextResponse.json({ error: 'Company name is required' }, { status: 400 });
    }
    
    // Convert company name to uppercase
    companyName = companyName.toUpperCase().trim();
    
    if (!companyName) {
      return NextResponse.json({ error: 'Company name is required' }, { status: 400 });
    }
    
    // Create company directory
    const companyDir = path.join(process.cwd(), 'knowledge', companyName);
    
    // Check if company already exists
    if (await fs.pathExists(companyDir)) {
      return NextResponse.json({ error: `Company "${companyName}" already exists` }, { status: 400 });
    }
    
    await fs.ensureDir(companyDir);
    
    return NextResponse.json({ 
      message: 'Company created successfully',
      company: {
        id: companyName,
        name: companyName,
        contracts: []
      }
    });
  } catch (error) {
    console.error('Create company error:', error);
    return NextResponse.json({ error: 'Failed to create company' }, { status: 500 });
  }
}