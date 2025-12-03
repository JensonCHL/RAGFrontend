import { NextRequest, NextResponse } from 'next/server';
import fs from 'fs-extra';
import path from 'path';

export async function POST(request: NextRequest) {
  try {
    const formData = await request.formData();
    const file = formData.get('file') as File;
    let companyName = formData.get('companyName') as string;
    
    if (!companyName) {
      return NextResponse.json({ error: 'Company name is required' }, { status: 400 });
    }
    
    // Convert company name to uppercase
    companyName = companyName.toUpperCase().trim();
    
    if (!companyName) {
      return NextResponse.json({ error: 'Company name is required' }, { status: 400 });
    }
    
    if (!file) {
      return NextResponse.json({ error: 'No file provided' }, { status: 400 });
    }
    
    // Validate file type (PDF only)
    if (file.type !== 'application/pdf' && !file.name.toLowerCase().endsWith('.pdf')) {
      return NextResponse.json({ error: 'Only PDF files are allowed' }, { status: 400 });
    }
    
    // Create company directory if it doesn't exist
    const companyDir = path.join(process.cwd(), 'knowledge', companyName);
    await fs.ensureDir(companyDir);
    
    // Save the file
    const filePath = path.join(companyDir, file.name);
    
    // Check if file already exists
    const fileExists = await fs.pathExists(filePath);
    
    const bytes = await file.arrayBuffer();
    await fs.writeFile(filePath, Buffer.from(bytes));
    
    return NextResponse.json({ 
      success: true,
      message: 'File uploaded successfully',
      file: {
        name: file.name,
        size: file.size,
        type: file.type,
        overwritten: fileExists
      },
      companyName
    });
  } catch (error) {
    console.error('Upload error:', error);
    return NextResponse.json({ 
      success: false,
      error: 'Failed to upload file' 
    }, { status: 500 });
  }
}
