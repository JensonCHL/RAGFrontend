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

    // Clear any previous errors
    setError(null);

    // Process each folder
    let successCount = 0;
    let failCount = 0;
    
    for (const folderEntry of folderEntries) {
      try {
        await processFolderEntry(folderEntry);
        successCount++;
      } catch (err) {
        console.error('Error processing folder:', folderEntry.name, err);
        failCount++;
      }
    }
    
    // Show summary if there were failures
    if (failCount > 0) {
      const message = `Processed ${successCount} folders successfully. ${failCount} folders had issues.`;
      setError(message);
    }
  };

  const processFolderEntry = async (folderEntry: any) => {
    try {
      // Recursive function to get all PDF files from nested folders
      const getAllPdfFiles = async (entry: any, files: File[] = []): Promise<File[]> => {
        if (entry.isFile) {
          return new Promise((resolve) => {
            entry.file((file: File) => {
              // Only collect PDF files
              if (file.type === 'application/pdf' || file.name.toLowerCase().endsWith('.pdf')) {
                files.push(file);
              }
              resolve(files);
            });
          });
        } else if (entry.isDirectory) {
          // Recursively process directory contents
          const dirReader = entry.createReader();
          
          return new Promise((resolve) => {
            const readAllEntries = () => {
              dirReader.readEntries(async (entries: any[]) => {
                if (entries.length === 0) {
                  resolve(files);
                } else {
                  // Process all entries in current directory
                  for (const childEntry of entries) {
                    await getAllPdfFiles(childEntry, files);
                  }
                  // Continue reading if there are more entries
                  readAllEntries();
                }
              });
            };
            readAllEntries();
          });
        }
        return files;
      };

      // Extract all PDF files from folder and subfolders
      const allPdfFiles: File[] = [];
      await getAllPdfFiles(folderEntry, allPdfFiles);

      if (allPdfFiles.length === 0) {
        console.warn(`No PDF files found in folder "${folderEntry.name}" and its subfolders`);
        // Continue processing other folders instead of stopping
        return;
      }

      // if (allPdfFiles.length > 20) {
      //   setError(`Too many PDF files (${allPdfFiles.length}) found. Please ensure folder contains maximum of 20 PDF files.`);
      //   return;
      // }

      // Use directory name as company name (convert to uppercase)
      onFolderUpload(folderEntry.name.toUpperCase(), allPdfFiles);
    } catch (err) {
      console.error('Error processing folder:', folderEntry.name, err);
      // Log error but continue processing other folders
      // Don't set global error that stops everything
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
              Folders with files (nested folders allowed)
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
            <li>Folders with PDF files</li>
            <li>Nested subfolders are allowed (PDFs will be flattened)</li>
            <li>Maximum 20 PDF files per folder</li>
            <li>Folder names become company names</li>
          </ul>
        </div>
      </div>
    </div>
  );
}