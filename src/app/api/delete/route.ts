import { NextRequest, NextResponse } from 'next/server';
import fs from 'fs-extra';
import path from 'path';

export async function DELETE(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url);
    const companyName = searchParams.get('companyName');
    const fileName = searchParams.get('fileName');
    
    if (!companyName) {
      return NextResponse.json({ error: 'Company name is required' }, { status: 400 });
    }
    
    const companyDir = path.join(process.cwd(), 'knowledge', companyName);
    
    // Check if company directory exists
    if (!(await fs.pathExists(companyDir))) {
      return NextResponse.json({ error: 'Company not found' }, { status: 404 });
    }
    
    if (fileName) {
      // Delete specific file
      const filePath = path.join(companyDir, fileName);
      
      if (!(await fs.pathExists(filePath))) {
        return NextResponse.json({ error: 'File not found' }, { status: 404 });
      }
      
      await fs.unlink(filePath);
      return NextResponse.json({ message: 'File deleted successfully' });
    } else {
      // Delete entire company directory
      await fs.remove(companyDir);
      return NextResponse.json({ message: 'Company folder deleted successfully' });
    }
  } catch (error) {
    console.error('Delete error:', error);
    return NextResponse.json({ error: 'Failed to delete' }, { status: 500 });
  }
}