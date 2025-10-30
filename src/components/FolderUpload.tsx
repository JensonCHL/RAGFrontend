'use client';

import { useState, useRef } from 'react';

interface FolderUploadProps {
  onFolderUpload: (folderName: string, files: File[]) => void;
}

export default function FolderUpload({ onFolderUpload }: FolderUploadProps) {
  const [isDragging, setIsDragging] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleDragEnter = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
  };

  const handleDrop = async (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
    setError(null);

    if (e.dataTransfer.items && e.dataTransfer.items.length > 0) {
      // Handle folder drops using webkitGetAsEntry
      const items = Array.from(e.dataTransfer.items);
      const entries = items.map(item => item.webkitGetAsEntry()).filter(entry => entry !== null);
      
      if (entries.length > 0) {
        await processEntries(entries);
      } else {
        // Fallback to file list if entries not available
        const files = Array.from(e.dataTransfer.files);
        await processFiles(files);
      }
      
      e.dataTransfer.clearData();
    } else if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      // Fallback to file list
      const files = Array.from(e.dataTransfer.files);
      await processFiles(files);
      e.dataTransfer.clearData();
    }
  };

  const processEntries = async (entries: any[]) => {
    // Filter out file entries and only process folder entries
    const folderEntries = entries.filter(entry => entry.isDirectory);
    const fileEntries = entries.filter(entry => entry.isFile);
    
    if (folderEntries.length === 0 && fileEntries.length > 0) {
      setError('Please drop folders, not individual files. Create folders and put your files inside them.');
      return;
    }
    
    // Process each folder
    for (const folderEntry of folderEntries) {
      await processFolderEntry(folderEntry);
    }
  };

  const processFolderEntry = async (folderEntry: any) => {
    try {
      // Read all entries in the folder
      const dirReader = folderEntry.createReader();
      const entries: any[] = [];
      
      // Read all entries in the directory
      const readEntries = () => {
        return new Promise<void>((resolve) => {
          dirReader.readEntries((results: any[]) => {
            if (results.length === 0) {
              resolve();
            } else {
              entries.push(...results);
              readEntries().then(resolve);
            }
          });
        });
      };
      
      await readEntries();
      
      // Check for nested folders
      const subFolderEntries = entries.filter(entry => entry.isDirectory);
      if (subFolderEntries.length > 0) {
        setError('Nested folders are not allowed. Please upload folders with files directly inside them.');
        return;
      }
      
      // Extract all files (any type)
      const allFiles: File[] = [];
      const promises = entries.map(async (childEntry) => {
        if (childEntry.isFile) {
          return new Promise<void>((resolve) => {
            childEntry.file((file: File) => {
              allFiles.push(file);
              resolve();
            });
          });
        }
      });
      
      await Promise.all(promises);
      
      if (allFiles.length === 0) {
        setError(`No files found in folder "${folderEntry.name}"`);
        return;
      }
      
      if (allFiles.length > 20) {
        setError(`Too many files (${allFiles.length}) in folder "${folderEntry.name}". Please upload a maximum of 20 files per folder.`);
        return;
      }
      
      // Use directory name as company name (convert to uppercase)
      onFolderUpload(folderEntry.name.toUpperCase(), allFiles);
    } catch (err) {
      console.error('Error processing folder:', err);
      setError('Failed to process folder. Please try again.');
    }
  };

  const processFiles = async (files: File[]) => {
    setError('Please drop folders, not individual files. Create folders and put your files inside them.');
  };

  const handleClick = () => {
    if (fileInputRef.current) {
      fileInputRef.current.click();
    }
  };

  const handleFileInputChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      const files = Array.from(e.target.files);
      
      if (files.length === 0) {
        setError('No files selected');
        return;
      }
      
      // Group files by their parent folder
      const folders: Record<string, File[]> = {};
      
      files.forEach(file => {
        // Get the parent folder name from webkitRelativePath
        const pathParts = file.webkitRelativePath.split('/');
        if (pathParts.length >= 2) {
          const folderName = pathParts[0];
          if (!folders[folderName]) {
            folders[folderName] = [];
          }
          folders[folderName].push(file);
        }
      });
      
      // Validate each folder
      for (const [folderName, folderFiles] of Object.entries(folders)) {
        if (folderFiles.length > 20) {
          setError(`Too many files (${folderFiles.length}) in folder "${folderName}". Please select a maximum of 20 files per folder.`);
          return;
        }
      }
      
      // Process each folder
      for (const [folderName, folderFiles] of Object.entries(folders)) {
        onFolderUpload(folderName.toUpperCase(), folderFiles);
      }
      
      e.target.value = ''; // Reset input
    }
  };

  return (
    <div className="bg-white rounded-lg shadow">
      <div className="p-4">
        <h2 className="text-md font-semibold text-gray-800 mb-2">Upload Company Folders</h2>
        <p className="text-gray-600 text-xs mb-3">
          Drag and drop folders containing files, or click to select folders
        </p>
        
        <div 
          className={`border border-dashed rounded-md p-4 text-center cursor-pointer transition-all duration-150 ${
            isDragging 
              ? 'border-blue-500 bg-blue-50' 
              : 'border-gray-300 hover:border-gray-400'
          }`}
          onDragEnter={handleDragEnter}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          onClick={handleClick}
        >
          <div className="flex flex-col items-center justify-center">
            <svg 
              className="w-8 h-8 text-gray-400 mb-2" 
              fill="none" 
              stroke="currentColor" 
              viewBox="0 0 24 24" 
              xmlns="http://www.w3.org/2000/svg"
            >
              <path 
                strokeLinecap="round" 
                strokeLinejoin="round" 
                strokeWidth="2" 
                d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"
              ></path>
            </svg>
            <p className="text-gray-600 text-sm">
              <span className="font-medium text-blue-600">Click to upload</span> or drag and drop
            </p>
            <p className="text-gray-500 text-xs mt-1">
              Folders with files (no nested folders)
            </p>
          </div>
          
          <input
            type="file"
            ref={fileInputRef}
            className="hidden"
            multiple
            onChange={handleFileInputChange}
            {...({webkitdirectory: true} as any)}
          />
        </div>
        
        {error && (
          <div className="mt-2 text-red-500 text-xs">{error}</div>
        )}
        
        <div className="mt-3 text-xs text-gray-500">
          <p>Requirements:</p>
          <ul className="list-disc list-inside mt-1 space-y-1">
            <li>Folders with files of any type</li>
            <li>No nested subfolders allowed</li>
            <li>Maximum 20 files per folder</li>
            <li>Folder names become company names</li>
          </ul>
        </div>
      </div>
    </div>
  );
}