import { NextRequest, NextResponse } from 'next/server';
import fs from 'fs-extra';
import path from 'path';

export async function GET() {
  try {
    const knowledgeDir = path.join(process.cwd(), 'knowledge');
    
    // Check if knowledge directory exists
    if (!(await fs.pathExists(knowledgeDir))) {
      return NextResponse.json({ companies: [] });
    }
    
    // Get all company directories
    const companyNames = await fs.readdir(knowledgeDir);
    const companies = [];
    
    for (const companyName of companyNames) {
      const companyPath = path.join(knowledgeDir, companyName);
      const stat = await fs.stat(companyPath);
      
      if (stat.isDirectory()) {
        // Get all files in the company directory
        const files = await fs.readdir(companyPath);
        const contractFiles = [];
        
        for (const fileName of files) {
          const filePath = path.join(companyPath, fileName);
          const fileStat = await fs.stat(filePath);
          
          if (fileStat.isFile()) {
            contractFiles.push({
              name: fileName,
              size: fileStat.size,
              uploadDate: fileStat.birthtime.toISOString(),
            });
          }
        }
        
        companies.push({
          id: companyName,
          name: companyName.toUpperCase(), // Always return uppercase
          contracts: contractFiles,
        });
      }
    }
    
    // Sort companies alphabetically by name
    companies.sort((a, b) => a.name.localeCompare(b.name));
    
    return NextResponse.json({ companies });
  } catch (error) {
    console.error('Error fetching companies:', error);
    return NextResponse.json({ error: 'Failed to fetch companies' }, { status: 500 });
  }
}