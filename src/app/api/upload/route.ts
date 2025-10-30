import { NextRequest, NextResponse } from 'next/server';
import fs from 'fs-extra';
import path from 'path';

export async function POST(request: NextRequest) {
  try {
    const formData = await request.formData();
    const files = formData.getAll('files') as File[];
    let companyName = formData.get('companyName') as string;
    
    if (!companyName) {
      return NextResponse.json({ error: 'Company name is required' }, { status: 400 });
    }
    
    // Convert company name to uppercase
    companyName = companyName.toUpperCase().trim();
    
    if (!companyName) {
      return NextResponse.json({ error: 'Company name is required' }, { status: 400 });
    }
    
    if (!files || files.length === 0) {
      return NextResponse.json({ error: 'No files provided' }, { status: 400 });
    }
    
    if (files.length > 20) {
      return NextResponse.json({ error: 'Too many files. Maximum 20 files allowed per upload.' }, { status: 400 });
    }
    
    // Create company directory if it doesn't exist
    const companyDir = path.join(process.cwd(), 'knowledge', companyName);
    await fs.ensureDir(companyDir);
    
    // Save each file
    const savedFiles = [];
    for (const file of files) {
      const filePath = path.join(companyDir, file.name);
      
      // Check if file already exists
      const fileExists = await fs.pathExists(filePath);
      
      const bytes = await file.arrayBuffer();
      await fs.writeFile(filePath, Buffer.from(bytes));
      savedFiles.push({
        name: file.name,
        size: file.size,
        type: file.type,
        overwritten: fileExists
      });
    }
    
    return NextResponse.json({ 
      message: 'Files uploaded successfully',
      files: savedFiles,
      companyName
    });
  } catch (error) {
    console.error('Upload error:', error);
    return NextResponse.json({ error: 'Failed to upload files' }, { status: 500 });
  }
}