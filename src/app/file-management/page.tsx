'use client';

import { useState, useEffect } from 'react';
import CompanyCard from '@/components/CompanyCard';
import FolderUpload from '@/components/FolderUpload';
import CompanyCreationForm from '@/components/CompanyCreationForm';
import ProcessingProgressDisplay from '@/components/ProcessingProgressDisplay';
import Link from 'next/link';
import { Contract, Company, QdrantDocumentMetadata, QdrantCompany, ProcessingState } from '@/types';

const toCamel = (s: string) => {
  return s.replace(/([-_][a-z])/ig, ($1) => {
    return $1.toUpperCase()
      .replace('-', '')
      .replace('_', '');
  });
};

const convertKeysToCamelCase = (obj: any): any => {
  if (Array.isArray(obj)) {
    return obj.map(v => convertKeysToCamelCase(v));
  } else if (obj !== null && typeof obj === 'object') {
    return Object.keys(obj).reduce((result: {[key: string]: any}, key: string) => {
      result[toCamel(key)] = convertKeysToCamelCase(obj[key]);
      return result;
    }, {});
  }
  return obj;
};

export default function FileManagementPage() {
  const [companies, setCompanies] = useState<Company[]>([]);
  const [isCreatingCompany, setIsCreatingCompany] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [qdrantData, setQdrantData] = useState<Record<string, QdrantCompany>>({});
  const [loadingQdrant, setLoadingQdrant] = useState(true);
  const [uploadProgress, setUploadProgress] = useState<number | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [selectedCompany, setSelectedCompany] = useState<Company | null>(null);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [isModalDragging, setIsModalDragging] = useState(false);
  const [processingStates, setProcessingStates] = useState<Record<string, ProcessingState>>({});

  // Fetch companies from API
  useEffect(() => {
    fetchCompanies();
  }, []);

  // Fetch Qdrant data
  useEffect(() => {
    fetchQdrantData();
  }, []);

  // Helper function to get deduplicated processing states for a company
  const getDeduplicatedProcessingStates = (companyId: string) => {
    // Filter processing states for the selected company that are currently active or in error
    const companyStates = Object.values(processingStates)
      .filter(state => state.companyId === companyId && (state.isProcessing || state.isError));
    
    // Group by currentFile to avoid duplicates
    const groupedStates: Record<string, ProcessingState[]> = {};
    companyStates.forEach(state => {
      const fileKey = state.currentFile || 'unknown';
      if (!groupedStates[fileKey]) {
        groupedStates[fileKey] = [];
      }
      groupedStates[fileKey].push(state);
    });
    
    // For each file, show the most recently updated state
    const deduplicatedStates = Object.values(groupedStates).map(states => {
      // Sort by progress or timestamp to get the most recent
      return states.reduce((latest, current) => {
        // Prefer the one with higher progress
        if ((current.progress || 0) > (latest.progress || 0)) {
          return current;
        }
        // Or prefer the one with more completed pages
        if ((current.completedPages || 0) > (latest.completedPages || 0)) {
          return current;
        }
        return latest;
      });
    });
    
    return deduplicatedStates;
  };

  // Fetch all processing states once when component mounts
  useEffect(() => {
    // Initialize with a single fetch
    const fetchInitialProcessingStates = async () => {
      try {
        const response = await fetch(`http://localhost:5000/api/document-processing-states?t=${new Date().getTime()}`);
        const allStates = await response.json();
        setProcessingStates(convertKeysToCamelCase(allStates));
      } catch (error) {
        console.error('Failed to fetch initial processing states:', error);
      }
    };
    fetchInitialProcessingStates();

    // Set up SSE for real-time updates
    let eventSource: EventSource | null = null;

    const setupEventSource = () => {
      eventSource = new EventSource('http://localhost:5000/events/processing-updates');

      eventSource.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);

          // Handle different types of messages
          if (data.type === 'states_updated') {
            const newStates = convertKeysToCamelCase(data.states);
            setProcessingStates(prev => ({ ...prev, ...newStates }));
          } else if (data.type === 'page_started' || data.type === 'page_completed') {
            // Update page-level progress for the specific document
            setProcessingStates(prev => {
              const updated = { ...prev };

              // Find the document with matching currentFile
              Object.entries(updated).forEach(([docId, state]) => {
                if (state.currentFile === data.document) {
                  updated[docId] = {
                    ...state,
                    currentPage: data.page,
                    totalPages: data.total_pages,
                    completedPages: data.completed_pages || state.completedPages
                  };
                }
              });

              return updated;
            });
          }
        } catch (error) {
          console.error('Failed to parse SSE message:', error);
        }
      };

      eventSource.onerror = (error) => {
        console.error('SSE error:', error);
        // Reconnect after 5 seconds
        setTimeout(setupEventSource, 5000);
      };
    };

    setupEventSource();

    // Cleanup function
    return () => {
      if (eventSource) {
        eventSource.close();
      }
    };
  }, []);

  const fetchCompanies = async () => {
    try {
      setIsLoading(true);
      setError(null);
      const response = await fetch('/api/companies');
      const data = await response.json();
      
      if (data.error) {
        setError(data.error);
        setCompanies([]);
      } else {
        // Convert company names to uppercase and sort alphabetically
        const formattedCompanies = (data.companies || []).map((company: Company) => ({
          ...company,
          name: company.name.toUpperCase()
        })).sort((a: Company, b: Company) => a.name.localeCompare(b.name));
        
        setCompanies(formattedCompanies);
      }
    } catch (error) {
      console.error('Failed to fetch companies:', error);
      setError('Failed to load companies');
      setCompanies([]);
    } finally {
      setIsLoading(false);
    }
  };

  const fetchQdrantData = async () => {
    try {
      setLoadingQdrant(true);
      const response = await fetch('http://localhost:5000/api/companies-with-documents');
      const data = await response.json();
      
      console.log('Fetched Qdrant data:', data); // Debug log

      if (data.success) {
        // Transform the data into a record for easy lookup
        const qdrantRecord: Record<string, QdrantCompany> = {};
        Object.entries(data.data).forEach(([name, documents]) => {
          qdrantRecord[name.toUpperCase()] = {
            name: name.toUpperCase(),
            documents: documents as Record<string, QdrantDocumentMetadata>
          };
        });
        setQdrantData(qdrantRecord);
      }
    } catch (err) {
      console.error('Error fetching Qdrant data:', err);
      setError('Failed to load processed document data');
    } finally {
      setLoadingQdrant(false);
    }
  };

  const handleFolderUpload = async (folderName: string, files: File[]) => {
    try {
      // Validate folder structure - reject nested folders
      const hasNestedFolders = files.some(file => {
        // Check if file path contains subdirectories
        return file.webkitRelativePath && file.webkitRelativePath.split('/').length > 2;
      });
      
      if (hasNestedFolders) {
        setError('Nested folders are not allowed. Please upload folders with files directly inside them.');
        return;
      }
      
      // Convert company name to uppercase
      const upperCaseFolderName = folderName.toUpperCase();
      
      // Check for duplicate company name
      const existingCompany = companies.find(company => company.name === upperCaseFolderName);
      if (existingCompany) {
        // Automatically add files to existing company without confirmation
        console.log(`Adding files to existing company: ${upperCaseFolderName}`);
      }
      
      const formData = new FormData();
      files.forEach(file => formData.append('files', file));
      formData.append('companyName', upperCaseFolderName);

      // Show upload progress
      setIsUploading(true);
      setUploadProgress(0);

      const xhr = new XMLHttpRequest();
      
      // Track upload progress
      xhr.upload.addEventListener('progress', (event) => {
        if (event.lengthComputable) {
          const percentComplete = Math.round((event.loaded / event.total) * 100);
          setUploadProgress(percentComplete);
        }
      });

      // Handle response
      const responsePromise = new Promise((resolve, reject) => {
        xhr.onload = function() {
          if (xhr.status >= 200 && xhr.status < 300) {
            resolve(xhr.response);
          } else {
            reject(new Error(`HTTP ${xhr.status}: ${xhr.statusText}`));
          }
        };
        
        xhr.onerror = function() {
          reject(new Error('Network error'));
        };
      });

      // Send request
      xhr.open('POST', '/api/upload');
      xhr.send(formData);

      // Wait for response
      await responsePromise;

      // Hide progress bar
      setUploadProgress(null);
      setIsUploading(false);

      // Refresh the company list
      await fetchCompanies();
      // Refresh Qdrant data
      await fetchQdrantData();
      setError(null);
    } catch (error) {
      console.error('Upload error:', error);
      setError('Upload failed. Please try again.');
      setUploadProgress(null);
      setIsUploading(false);
    }
  };

  const handleCreateCompany = async (companyName: string) => {
    try {
      // Convert company name to uppercase
      const upperCaseCompanyName = companyName.toUpperCase();
      
      // Check for duplicate company name
      const existingCompany = companies.find(company => company.name === upperCaseCompanyName);
      if (existingCompany) {
        setError(`Company "${upperCaseCompanyName}" already exists.`);
        return;
      }
      
      const response = await fetch('/api/create-company', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ companyName: upperCaseCompanyName }),
      });

      if (response.ok) {
        // Refresh the company list
        await fetchCompanies();
        setIsCreatingCompany(false);
        setError(null);
      } else {
        const error = await response.json();
        setError(error.error || 'Failed to create company');
      }
    } catch (error) {
      console.error('Create company error:', error);
      setError('Failed to create company. Please try again.');
    }
  };

  const handleDeleteCompany = async (companyId: string) => {
    // Remove confirmation dialog
    try {
      const response = await fetch(`/api/delete?companyName=${encodeURIComponent(companyId)}`, {
        method: 'DELETE',
      });

      if (response.ok) {
        // Refresh the company list
        await fetchCompanies();
        // Refresh Qdrant data
        await fetchQdrantData();
        setError(null);
      } else {
        const error = await response.json();
        setError(error.error || 'Failed to delete company');
      }
    } catch (error) {
      console.error('Delete company error:', error);
      setError('Failed to delete company. Please try again.');
    }
  };

  const handleDeleteContract = async (companyId: string, contractName: string) => {
    // Remove confirmation dialog
    try {
      const response = await fetch(`/api/delete?companyName=${encodeURIComponent(companyId)}&fileName=${encodeURIComponent(contractName)}`, {
        method: 'DELETE',
      });

      if (response.ok) {
        // Refresh the company list
        await fetchCompanies();
        // Refresh Qdrant data
        await fetchQdrantData();
        setError(null);
        
        // Update the selectedCompany state in the modal if it's open
        if (selectedCompany && selectedCompany.id === companyId) {
          setSelectedCompany(prev => {
            if (!prev) return null;
            return {
              ...prev,
              contracts: prev.contracts.filter(contract => contract.name !== contractName)
            };
          });
        }
      } else {
        const error = await response.json();
        setError(error.error || 'Failed to delete contract');
      }
    } catch (error) {
      console.error('Delete contract error:', error);
      setError('Failed to delete contract. Please try again.');
    }
  };

  const handleAddContracts = async (companyId: string, files: File[]) => {
    try {
      // Validate files - reject if any are in subfolders
      const hasNestedFolders = files.some(file => {
        return file.webkitRelativePath && file.webkitRelativePath.split('/').length > 2;
      });
      
      if (hasNestedFolders) {
        setError('Nested folders are not allowed. Please upload folders with files directly inside them.');
        return;
      }
      
      // Check for duplicate file names
      const company = companies.find(c => c.id === companyId);
      if (company) {
        const duplicateFiles = files.filter(file => 
          company.contracts.some(contract => contract.name === file.name)
        );
        
        if (duplicateFiles.length > 0) {
          // Automatically overwrite duplicate files without confirmation
          console.log(`Overwriting ${duplicateFiles.length} duplicate files`);
        }
      }
      
      const formData = new FormData();
      files.forEach(file => formData.append('files', file));
      formData.append('companyName', companyId);

      // Show upload progress
      setIsUploading(true);
      setUploadProgress(0);

      const xhr = new XMLHttpRequest();
      
      // Track upload progress
      xhr.upload.addEventListener('progress', (event) => {
        if (event.lengthComputable) {
          const percentComplete = Math.round((event.loaded / event.total) * 100);
          setUploadProgress(percentComplete);
        }
      });

      // Handle response
      const responsePromise = new Promise((resolve, reject) => {
        xhr.onload = function() {
          if (xhr.status >= 200 && xhr.status < 300) {
            resolve(xhr.response);
          } else {
            reject(new Error(`HTTP ${xhr.status}: ${xhr.statusText}`));
          }
        };
        
        xhr.onerror = function() {
          reject(new Error('Network error'));
        };
      });

      // Send request
      xhr.open('POST', '/api/upload');
      xhr.send(formData);

      // Wait for response
      await responsePromise;

      // Hide progress bar
      setUploadProgress(null);
      setIsUploading(false);

      // Refresh the company list
      await fetchCompanies();
      // Refresh Qdrant data
      await fetchQdrantData();
      setError(null);
      
      // Update the selectedCompany state in the modal if it's open
      if (selectedCompany && selectedCompany.id === companyId) {
        // Refresh the selected company data
        const updatedCompaniesResponse = await fetch('/api/companies');
        const updatedCompaniesData = await updatedCompaniesResponse.json();
        if (updatedCompaniesData.companies) {
          const updatedCompany = updatedCompaniesData.companies.find((c: Company) => c.id === companyId);
          if (updatedCompany) {
            setSelectedCompany({
              ...updatedCompany,
              name: updatedCompany.name.toUpperCase()
            });
          }
        }
      }
    } catch (error) {
      console.error('Upload contracts error:', error);
      setError('Failed to upload contracts. Please try again.');
      setUploadProgress(null);
      setIsUploading(false);
    }
  };

  const handleProcessUnsyncedDocuments = async (companyId: string) => {
    try {
      // Get the company data
      const company = companies.find(c => c.id === companyId);
      if (!company) {
        setError('Company not found');
        return;
      }

      // Get unsynced documents
      const qdrantCompanyData = qdrantData[company.name];
      const syncedDocs = qdrantCompanyData ? Object.keys(qdrantCompanyData.documents) : [];
      const unsyncedDocs = company.contracts.filter(contract => !syncedDocs.includes(contract.name));

      if (unsyncedDocs.length === 0) {
        setError('No unsynced documents found');
        return;
      }

      // Prepare the files list for the API
      const filesToProcess = unsyncedDocs.map(doc => doc.name);

      // Call the new processing API endpoint
      const response = await fetch('http://localhost:5000/api/process-documents', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          company_id: companyId,
          files: filesToProcess
        })
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      if (!response.body) {
        throw new Error('ReadableStream not supported in this browser.');
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();

      try {
        let buffer = '';
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          
          // Process complete JSON lines
          const lines = buffer.split('\n');
          buffer = lines.pop() || ''; // Keep incomplete line in buffer

          for (const line of lines) {
            if (line.trim()) {
              try {
                const data = JSON.parse(line);
                
                // Handle error responses
                if (data.error) {
                  throw new Error(data.error);
                }
                
                // Handle process errors
                if (data.status === "process_error" || data.status === "step_failed") {
                  throw new Error(data.error || 'Processing failed');
                }

                // Optimistic UI update: Mark document as synced immediately after ingestion completes
                if (data.status === "ingestion_completed") {
                  const { company, document } = data;
                  if (company && document) {
                    setQdrantData(prevQdrantData => {
                      const newQdrantData = { ...prevQdrantData };
                      const upperCaseCompany = company.toUpperCase();

                      if (!newQdrantData[upperCaseCompany]) {
                        newQdrantData[upperCaseCompany] = {
                          name: upperCaseCompany,
                          documents: {}
                        };
                      }
                      // Add a dummy DocumentMetadata for immediate visual feedback
                      newQdrantData[upperCaseCompany].documents[document] = {
                        doc_id: 'optimistic', // Placeholder
                        upload_time: new Date().toISOString(), // Placeholder
                        pages: [] // Placeholder
                      };
                      return newQdrantData;
                    });
                  }
                }
                
                // Update processing state based on the response
                setProcessingStates(prev => ({
                  ...prev,
                  [data.doc_id]: {
                    ...prev[data.doc_id],
                    isProcessing: data.status !== "all_completed" && data.status !== "process_error" && data.status !== "step_failed",
                    isError: data.status === "process_error" || data.status === "step_failed",
                    errorMessage: data.error || prev[data.doc_id]?.errorMessage,
                    currentFile: data.currentFile || prev[data.doc_id]?.currentFile,
                    fileIndex: data.file_index || prev[data.doc_id]?.fileIndex,
                    totalFiles: data.total_files || prev[data.doc_id]?.totalFiles,
                    progress: data.progress !== undefined ? data.progress : prev[data.doc_id]?.progress,
                    message: data.message || prev[data.doc_id]?.message,
                    currentStep: data.step || prev[data.doc_id]?.currentStep,
                    ocrProgress: data.ocrProgress || prev[data.doc_id]?.ocrProgress,
                    embeddingProgress: data.embeddingProgress || prev[data.doc_id]?.embeddingProgress,
                    ingestionProgress: data.ingestionProgress || prev[data.doc_id]?.ingestionProgress,
                    companyId: companyId, // Ensure companyId is present
                    doc_id: data.doc_id // Ensure doc_id is present in the state object
                  }
                }));
              } catch (parseError) {
                console.warn('Failed to parse JSON line:', line);
              }
            }
          }
        }
      } finally {
        reader.releaseLock();
      }

      // Refresh Qdrant data after processing
      await fetchQdrantData();
      
      // Update the selectedCompany state in the modal if it's open
      if (selectedCompany && selectedCompany.id === companyId) {
        // Refresh Qdrant data for the modal
        const updatedQdrantData = await fetch('http://localhost:5000/api/companies-with-documents').then(res => res.json());
        if (updatedQdrantData.success) {
          const qdrantRecord: Record<string, QdrantCompany> = {};
          Object.entries(updatedQdrantData.data).forEach(([name, documents]) => {
            qdrantRecord[name.toUpperCase()] = {
              name: name.toUpperCase(),
              documents: documents as Record<string, QdrantDocumentMetadata>
            };
          });
          setQdrantData(qdrantRecord);
        }
      }
      
      // Keep processing state for 5 seconds after completion so users can see the final status
      // We don't delete by companyId anymore since states are keyed by doc_id
      // The SSE updates will eventually clean up completed states
      
    } catch (error) {
      console.error('Process unsynced documents error:', error);
      setError(`Failed to process unsynced documents: ${error instanceof Error ? error.message : 'Unknown error'}`);
      
      // Update processing state to show error - we don't have doc_id here, so we can't update specific state
      // The SSE updates will eventually reflect the error state
      
      // Clear error message after 10 seconds
      setTimeout(() => {
        setError(null);
      }, 10000);
    }
  };

  // Drag and drop handlers for modal
  const handleModalDragEnter = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsModalDragging(true);
  };

  const handleModalDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsModalDragging(false);
  };

  const handleModalDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
  };

  const handleModalDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsModalDragging(false);
    
    if (selectedCompany && e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      const files = Array.from(e.dataTransfer.files);
      handleAddContracts(selectedCompany.id, files);
      e.dataTransfer.clearData();
    }
  };

  const openCompanyModal = (company: Company) => {
    setSelectedCompany(company);
    setIsModalOpen(true);
  };

  const closeCompanyModal = () => {
    setIsModalOpen(false);
    setSelectedCompany(null);
  };

  // Format file size for display
  const formatFileSize = (bytes: number): string => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  // Format date for display
  const formatDate = (dateString: string): string => {
    // Use a fixed locale to avoid hydration mismatches
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      timeZone: 'UTC'
    });
  };

  // Filter companies based on search term
  const filteredCompanies = companies.filter(company => {
    if (!searchTerm.trim()) return true;
    
    const term = searchTerm.toLowerCase();
    return (
      company.name.toLowerCase().includes(term) ||
      company.contracts.some(contract => 
        contract.name.toLowerCase().includes(term)
      )
    );
  });

  if (isLoading) {
    return (
      <div className="min-h-screen bg-gray-50 p-8">
        <div className="max-w-7xl mx-auto">
          <header className="mb-8">
            <div className="flex justify-between items-center">
              <div>
                <h1 className="text-3xl font-bold text-gray-900">File Management</h1>
                <p className="text-gray-600 mt-2">
                  Manage company folders and contracts
                </p>
              </div>
              <Link 
                href="/dashboard"
                className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
              >
                <svg className="mr-2 -ml-1 h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"></path>
                </svg>
                View Processed Documents
              </Link>
            </div>
          </header>

          <div className="bg-white rounded-lg shadow p-8 flex justify-center items-center">
            <div className="text-center">
              <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
              <p className="mt-4 text-gray-600">Loading companies...</p>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 p-8">
      <div className="max-w-7xl mx-auto">
        <header className="mb-8">
          <div className="flex justify-between items-center">
            <div>
              <h1 className="text-3xl font-bold text-gray-900">File Management</h1>
              <p className="text-gray-600 mt-2">
                Manage company folders and contracts
              </p>
            </div>
            <Link 
              href="/dashboard"
              className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
            >
              <svg className="mr-2 -ml-1 h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"></path>
              </svg>
              View Processed Documents
            </Link>
          </div>
        </header>

        {/* Upload Section - Moved to Top */}
        <div className="mb-8">
          <FolderUpload onFolderUpload={handleFolderUpload} />
        </div>

        {/* Upload Progress Bar */}
        {isUploading && uploadProgress !== null && (
          <div className="mb-6">
            <div className="bg-white rounded-lg shadow p-4">
              <div className="flex justify-between mb-1">
                <span className="text-sm font-medium text-gray-700">Uploading files...</span>
                <span className="text-sm font-medium text-gray-700">{uploadProgress}%</span>
              </div>
              <div className="w-full bg-gray-200 rounded-full h-2.5">
                <div 
                  className="bg-blue-600 h-2.5 rounded-full transition-all duration-300 ease-out"
                  style={{ width: `${uploadProgress}%` }}
                ></div>
              </div>
            </div>
          </div>
        )}

        {/* Search Bar - Moved below Upload Section */}
        <div className="mb-6">
          <div className="relative max-w-md">
            <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
              <svg className="h-5 w-5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"></path>
              </svg>
            </div>
            <input
              type="text"
              className="block w-full pl-10 pr-3 py-2 border border-gray-300 rounded-md leading-5 bg-white placeholder-gray-500 focus:outline-none focus:placeholder-gray-400 focus:ring-1 focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
              placeholder="Search companies or contracts..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
            />
          </div>
        </div>

        {/* Error Message */}
        {error && (
          <div className="mb-6 bg-red-50 border border-red-200 rounded-md p-4">
            <div className="flex">
              <div className="shrink-0">
                <svg className="h-5 w-5 text-red-400" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor">
                  <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
                </svg>
              </div>
              <div className="ml-3">
                <h3 className="text-sm font-medium text-red-800">Error</h3>
                <div className="mt-2 text-sm text-red-700">
                  <p>{error}</p>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Companies Section */}
        <div className="mb-6">
          <div className="flex justify-between items-center">
            <h2 className="text-xl font-semibold text-gray-800 flex items-center">
              Companies ({filteredCompanies.length})
              {loadingQdrant && (
                <svg className="animate-spin ml-2 h-4 w-4 text-blue-600" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
              )}
            </h2>
            {!isCreatingCompany ? (
              <button
                onClick={() => setIsCreatingCompany(true)}
                className="py-2 px-4 bg-blue-600 hover:bg-blue-700 text-white font-medium rounded-lg transition duration-150 ease-in-out"
              >
                + Create New Company
              </button>
            ) : null}
          </div>
        </div>

        {isCreatingCompany && (
          <div className="mb-8">
            <CompanyCreationForm 
              onCreateCompany={handleCreateCompany} 
              onCancel={() => setIsCreatingCompany(false)} 
            />
          </div>
        )}

        {filteredCompanies.length === 0 ? (
          <div className="bg-white rounded-lg shadow p-8 text-center">
            <svg className="mx-auto h-12 w-12 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
            </svg>
            <h3 className="mt-4 text-lg font-medium text-gray-900">
              {searchTerm ? 'No matching companies found' : 'No companies found'}
            </h3>
            <p className="mt-2 text-gray-500">
              {searchTerm 
                ? `No companies or contracts match your search for "${searchTerm}".` 
                : 'Upload a folder or create a company to get started.'}
            </p>
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {filteredCompanies.map(company => (
              <CompanyCard
                key={company.id}
                company={company}
                qdrantData={qdrantData[company.name] || null}
                onDelete={handleDeleteCompany}
                onDeleteContract={handleDeleteContract}
                onAddContracts={handleAddContracts}
                onProcessUnsynced={handleProcessUnsyncedDocuments}
                onOpenModal={openCompanyModal}
                allProcessingStates={processingStates} // Pass all processing states
              />
            ))}
          </div>
        )}

        {/* Company Detail Modal */}
        {isModalOpen && selectedCompany && (
          <div className="fixed inset-0 z-50 overflow-y-auto">
            <div className="flex items-center justify-center min-h-screen pt-4 px-4 pb-20 text-center sm:block sm:p-0">
              {/* Background overlay with blur effect */}
              <div 
                className="fixed inset-0 bg-gray-500 bg-opacity-10 backdrop-blur-sm transition-opacity duration-300 ease-out" 
                aria-hidden="true"
                onClick={closeCompanyModal}
              ></div>

              {/* Modal container with scale transition */}
              <div 
                className="inline-block align-bottom bg-white rounded-lg text-left overflow-hidden shadow-2xl transform transition-all duration-300 ease-out sm:my-8 sm:align-middle sm:max-w-4xl sm:w-full scale-100 max-h-[90vh] overflow-hidden"
                role="dialog"
                aria-modal="true"
                aria-labelledby="modal-headline"
              >
                {/* Modal header */}
                <div className="bg-white px-4 pt-5 pb-4 sm:p-6 sm:pb-4">
                  <div className="sm:flex sm:items-start">
                    <div className="mx-auto shrink-0 flex items-center justify-center h-12 w-12 rounded-full bg-blue-100 sm:mx-0 sm:h-10 sm:w-10">
                      <svg 
                        className="h-6 w-6 text-blue-600" 
                        fill="none" 
                        stroke="currentColor" 
                        viewBox="0 0 24 24" 
                        xmlns="http://www.w3.org/2000/svg"
                      >
                        <path 
                          strokeLinecap="round" 
                          strokeLinejoin="round" 
                          strokeWidth="2" 
                          d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z"
                        ></path>
                      </svg>
                    </div>
                    <div className="mt-3 text-center sm:mt-0 sm:ml-4 sm:text-left w-full">
                      <h3 className="text-lg leading-6 font-medium text-gray-900" id="modal-headline">
                        {selectedCompany.name}
                      </h3>
                      <div className="mt-2">
                        <p className="text-sm text-gray-500">
                          {selectedCompany.contracts.length} document{selectedCompany.contracts.length !== 1 ? 's' : ''}
                        </p>
                      </div>
                    </div>
                  </div>
                </div>

                {/* Modal content */}
                <div className="bg-white px-4 pt-2 pb-4 sm:p-6 sm:pb-4 overflow-y-auto max-h-[60vh]">
                  {/* File upload area */}
                  <div 
                    className={`border-2 border-dashed rounded-lg p-6 text-center mb-6 cursor-pointer hover:border-blue-400 transition-colors ${isModalDragging ? 'border-blue-400 bg-blue-50' : 'border-gray-300'}`}
                    onClick={() => document.getElementById(`modal-file-input-${selectedCompany.id}`)?.click()}
                    onDragEnter={handleModalDragEnter}
                    onDragOver={handleModalDragOver}
                    onDragLeave={handleModalDragLeave}
                    onDrop={handleModalDrop}
                  >
                    <svg 
                      className="mx-auto h-12 w-12 text-gray-400" 
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
                    <div className="flex text-sm text-gray-600">
                      <span className="relative font-medium text-blue-600 hover:text-blue-500">
                        Upload files
                      </span>
                      <p className="pl-1">or drag and drop</p>
                    </div>
                    <p className="text-xs text-gray-500 mt-1">
                      Any file type accepted
                    </p>
                    <input
                      id={`modal-file-input-${selectedCompany.id}`}
                      type="file"
                      className="hidden"
                      multiple
                      onChange={(e) => {
                        if (e.target.files && e.target.files.length > 0) {
                          const files = Array.from(e.target.files);
                          handleAddContracts(selectedCompany.id, files);
                          e.target.value = ''; // Reset input
                        }
                      }}
                    />
                  </div>

                  {/* Processing Progress Bar */}
                  {selectedCompany && (
                    <div className="space-y-4">
                      {getDeduplicatedProcessingStates(selectedCompany.id).map(state => (
                        <div key={state.doc_id} className="mb-6 bg-blue-50 rounded-lg p-4 border border-blue-200">
                          <ProcessingProgressDisplay state={state} />
                        </div>
                      ))}
                    </div>
                  )}

                  {/* Documents list */}
                  <div>
                    <h4 className="text-md font-medium text-gray-900 mb-3">Documents</h4>
                    {selectedCompany.contracts.length > 0 ? (
                      <div className="grid grid-cols-1 gap-3">
                        {selectedCompany.contracts.map((contract) => {
                          const isSynced = qdrantData[selectedCompany.name]?.documents[contract.name];
                          return (
                            <div 
                              key={contract.name} 
                              className="flex items-center justify-between p-3 bg-gray-50 rounded-md hover:bg-gray-100"
                            >
                              <div className="flex items-center">
                                <div className="flex-shrink-0 w-8 h-10 bg-red-100 rounded flex items-center justify-center">
                                  <svg 
                                    className="w-4 h-4 text-red-600" 
                                    fill="none" 
                                    stroke="currentColor" 
                                    viewBox="0 0 24 24" 
                                    xmlns="http://www.w3.org/2000/svg"
                                  >
                                    <path 
                                      strokeLinecap="round" 
                                      strokeLinejoin="round" 
                                      strokeWidth="2" 
                                      d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
                                    ></path>
                                  </svg>
                                </div>
                                <div className="ml-3 min-w-0">
                                  <p className="text-sm font-medium text-gray-900 break-words">
                                    {contract.name}
                                  </p>
                                  <div className="flex items-center mt-1">
                                    <p className="text-xs text-gray-500">
                                      {formatFileSize(contract.size)}
                                    </p>
                                    <span className="mx-2 text-gray-300">•</span>
                                    <p className="text-xs text-gray-500">
                                      {formatDate(contract.uploadDate)}
                                    </p>
                                  </div>
                                </div>
                              </div>
                              <div className="flex items-center">
                                {isSynced ? (
                                  <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800 mr-2">
                                    Processed
                                  </span>
                                ) : (
                                  <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-yellow-100 text-yellow-800 mr-2">
                                    Pending
                                  </span>
                                )}
                                <button
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    handleDeleteContract(selectedCompany.id, contract.name);
                                  }}
                                  className="p-1 text-gray-400 hover:text-red-500"
                                >
                                  <svg 
                                    className="w-4 h-4" 
                                    fill="none" 
                                    stroke="currentColor" 
                                    viewBox="0 0 24 24" 
                                    xmlns="http://www.w3.org/2000/svg"
                                  >
                                    <path 
                                      strokeLinecap="round" 
                                      strokeLinejoin="round" 
                                      strokeWidth="2" 
                                      d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
                                    ></path>
                                  </svg>
                                </button>
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    ) : (
                      <div className="text-center py-8">
                        <svg 
                          className="mx-auto h-12 w-12 text-gray-400" 
                          fill="none" 
                          stroke="currentColor" 
                          viewBox="0 0 24 24" 
                          xmlns="http://www.w3.org/2000/svg"
                        >
                          <path 
                            strokeLinecap="round" 
                            strokeLinejoin="round" 
                            strokeWidth="2" 
                            d="M9 13h6m-3-3v6m-9 1V7a2 2 0 012-2h6l2 2h6a2 2 0 012 2v8a2 2 0 01-2 2H5a2 2 0 01-2-2z"
                          ></path>
                        </svg>
                        <h3 className="mt-2 text-sm font-medium text-gray-900">No documents</h3>
                        <p className="mt-1 text-sm text-gray-500">
                          Upload PDF files to get started
                        </p>
                      </div>
                    )}
                  </div>
                </div>

                {/* Modal footer */}
                <div className="bg-gray-50 px-4 py-3 sm:px-6 sm:flex sm:flex-row-reverse">
                  <button
                    type="button"
                    className="mt-3 w-full inline-flex justify-center rounded-md border border-gray-300 shadow-sm px-4 py-2 bg-white text-base font-medium text-gray-700 hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 sm:mt-0 sm:ml-3 sm:w-auto sm:text-sm"
                    onClick={closeCompanyModal}
                  >
                    Close
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
