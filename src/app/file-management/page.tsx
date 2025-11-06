'use client';

import { useState, useEffect } from 'react';
import CompanyCard from '@/components/CompanyCard';
import FolderUpload from '@/components/FolderUpload';
import CompanyCreationForm from '@/components/CompanyCreationForm';
import ProcessingProgressDisplay from '@/components/ProcessingProgressDisplay';
import UploadProgressBar from '@/components/UploadProgressBar';
import SearchBar from '@/components/SearchBar';
import ErrorMessage from '@/components/ErrorMessage';
import NoCompaniesFoundMessage from '@/components/NoCompaniesFoundMessage';
import CompanyDetailModal from '@/components/CompanyDetailModal';
import LoadingSpinner from '@/components/LoadingSpinner';
import Link from 'next/link';
import { Contract, Company, QdrantDocumentMetadata, QdrantCompany, ProcessingState } from '@/types';
import { convertKeysToCamelCase } from '@/utils/data-transformers';
import DefaultLayout from '../default-layout';

function FileManagementPage() {
  const [companies, setCompanies] = useState<Company[]>([]);
  const [isCreatingCompany, setIsCreatingCompany] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [isInitialLoad, setIsInitialLoad] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [qdrantData, setQdrantData] = useState<Record<string, QdrantCompany>>({});
  const [loadingQdrant, setLoadingQdrant] = useState(true);
  const [uploadProgress, setUploadProgress] = useState<number | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [selectedCompany, setSelectedCompany] = useState<Company | null>(null);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [processingStates, setProcessingStates] = useState<Record<string, ProcessingState>>({});
  const [selectedCompanies, setSelectedCompanies] = useState<string[]>([]);

  // Fetch companies from API
  useEffect(() => {
    const loadAllData = async () => {
      try {
        // Load companies
        const companiesResponse = await fetch('/api/companies');
        const companiesData = await companiesResponse.json();

        if (companiesData.error) {
          setError(companiesData.error);
          setCompanies([]);
        } else {
          // Convert company names to uppercase and sort alphabetically
          const formattedCompanies = (companiesData.companies || []).map((company: Company) => ({
            ...company,
            name: company.name.toUpperCase()
          })).sort((a: Company, b: Company) => a.name.localeCompare(b.name));

          setCompanies(formattedCompanies);
        }
      } catch (error) {
        console.error('Failed to fetch companies:', error);
        setError('Failed to load companies');
        setCompanies([]);
      }

      // Load Qdrant data
      try {
        const qdrantResponse = await fetch('http://backend:5001/api/companies-with-documents');
        const qdrantData = await qdrantResponse.json();

        if (qdrantData.success) {
          // Transform the data into a record for easy lookup
          const qdrantRecord: Record<string, QdrantCompany> = {};
          Object.entries(qdrantData.data).forEach(([name, documents]) => {
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
      }

      // Load processing states
      try {
        const response = await fetch(`http://backend:5001/api/document-processing-states?t=${new Date().getTime()}`);
        const allStates = await response.json();
        setProcessingStates(convertKeysToCamelCase(allStates));
      } catch (error) {
        console.error('Failed to fetch initial processing states:', error);
      }

      // Set loading to false after all data is loaded
      setIsLoading(false);
      setIsInitialLoad(false);
    };

    loadAllData();
  }, []);

  // Set up SSE for real-time updates
  useEffect(() => {
    // Don't set up SSE until initial load is complete
    if (isInitialLoad) {
      return;
    }

    let eventSource: EventSource | null = null;

    const setupEventSource = () => {
      eventSource = new EventSource('http://backend:5001/events/processing-updates');

      eventSource.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);

          // Handle different types of messages
          if (data.type === 'states_updated') {
            const newStates = convertKeysToCamelCase(data.states);
            setProcessingStates(prev => ({ ...prev, ...newStates }));
          } else if (data.type === 'qdrant_data_updated') {
            // Update qdrantData directly from the SSE message
            const newQdrantData = convertKeysToCamelCase(data.data);
            setQdrantData(newQdrantData);
            console.log('Qdrant data updated via SSE:', newQdrantData);
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
  }, [isInitialLoad]);

  const handleSelectionChange = (companyId: string, checked: boolean) => {
    // Check if the company is currently processing
    const companyProcessingStates = Object.values(processingStates).filter(
      (state) => state.companyId === companyId
    );

    const isAnyDocumentProcessing = companyProcessingStates.some(
      (state) => state.isProcessing
    );

    // Prevent selection if company is processing
    if (isAnyDocumentProcessing && checked) {
      return;
    }

    setSelectedCompanies(prev => {
      if (checked) {
        return [...prev, companyId];
      } else {
        return prev.filter(id => id !== companyId);
      }
    });
  };

  const handleSelectAllChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.checked) {
      // Filter out companies that are currently processing
      const selectableCompanyIds = visibleCompanyIds.filter((companyId: string) => {
        const companyProcessingStates = Object.values(processingStates).filter(
          (state) => state.companyId === companyId
        );

        const isAnyDocumentProcessing = companyProcessingStates.some(
          (state) => state.isProcessing
        );

        return !isAnyDocumentProcessing;
      });

      setSelectedCompanies(selectableCompanyIds);
    } else {
      setSelectedCompanies([]);
    }
  };

  const handleProcessSelected = async () => {
    setError(null);
    const jobs = selectedCompanies.map(companyId => {
      const company = companies.find(c => c.id === companyId);
      if (!company) return null;

      const qdrantCompanyData = qdrantData[company.name];
      const syncedDocs = qdrantCompanyData ? Object.keys(qdrantCompanyData.documents) : [];
      const unsyncedFiles = company.contracts
        .filter(contract => !syncedDocs.includes(contract.name))
        .map(doc => doc.name);

      if (unsyncedFiles.length > 0) {
        return {
          company_id: companyId,
          files: unsyncedFiles
        };
      }
      return null;
    }).filter((job): job is { company_id: string; files: string[] } => job !== null);

    if (jobs.length === 0) {
      setError('No unsynced documents found for the selected companies.');
      return;
    }

    // Call the API for each job in parallel
    try {
      await Promise.all(jobs.map(job =>
        fetch('http://backend:5001/api/process-documents', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          // The backend expects a single job object, not an array
          body: JSON.stringify(job)
        })
          .then(response => {
            if (!response.ok) {
              console.error(`Failed to start processing for ${job.company_id}`);
            }
          })
      ));

      // Deselect all after starting the jobs
      setSelectedCompanies([]);
    } catch (error) {
      console.error('Error dispatching batch processing jobs:', error);
      setError('An error occurred while starting the processing jobs.');
    }
  };

  const fetchCompanies = async () => {
    try {
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
    }
  };

  const fetchQdrantData = async () => {
    try {
      setLoadingQdrant(true);
      const response = await fetch('http://backend:5001/api/companies-with-documents');
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
        xhr.onload = function () {
          if (xhr.status >= 200 && xhr.status < 300) {
            resolve(xhr.response);
          } else {
            reject(new Error(`HTTP ${xhr.status}: ${xhr.statusText}`));
          }
        };

        xhr.onerror = function () {
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
        xhr.onload = function () {
          if (xhr.status >= 200 && xhr.status < 300) {
            resolve(xhr.response);
          } else {
            reject(new Error(`HTTP ${xhr.status}: ${xhr.statusText}`));
          }
        };

        xhr.onerror = function () {
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
      const response = await fetch('http://backend:5001/api/process-documents', {
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

      // The backend now handles streaming and updates the Qdrant data via SSE
      // The frontend will receive updates via the SSE connection

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

  const openCompanyModal = (company: Company) => {
    setSelectedCompany(company);
    setIsModalOpen(true);
  };

  const closeCompanyModal = () => {
    setIsModalOpen(false);
    setSelectedCompany(null);
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

  // Derived state for convenience - MUST be after filteredCompanies is defined
  const visibleCompanyIds = filteredCompanies.map(c => c.id);

  // Filter out processing companies from visibleCompanyIds for selection purposes
  const selectableCompanyIds = visibleCompanyIds.filter((companyId: string) => {
    const companyProcessingStates = Object.values(processingStates).filter(
      (state) => state.companyId === companyId
    );

    const isAnyDocumentProcessing = companyProcessingStates.some(
      (state) => state.isProcessing
    );

    return !isAnyDocumentProcessing;
  });

  const isAllSelected = selectableCompanyIds.length > 0 && selectedCompanies.length === selectableCompanyIds.length;

  // Check if all visible companies are processing (to disable Select All)
  const areAllCompaniesProcessing = visibleCompanyIds.length > 0 &&
    visibleCompanyIds.every((companyId: string) => {
      const companyProcessingStates = Object.values(processingStates).filter(
        (state) => state.companyId === companyId
      );

      return companyProcessingStates.some((state) => state.isProcessing);
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
              <LoadingSpinner size="large" color="#2563eb" className="mx-auto" />
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
        <UploadProgressBar isUploading={isUploading} progress={uploadProgress} />

        {/* Search Bar - Moved below Upload Section */}
        <SearchBar searchTerm={searchTerm} onSearchChange={(e) => setSearchTerm(e.target.value)} />

        {/* Error Message */}
        <ErrorMessage message={error} />

        {/* Companies Section */}
        <div className="mb-6">
          <div className="flex justify-between items-center">
            <h2 className="text-xl font-semibold text-gray-800 flex items-center">
              Companies ({filteredCompanies.length})
            </h2>
            <div className="flex items-center space-x-4">
              {!isCreatingCompany && (
                <button
                  onClick={() => setIsCreatingCompany(true)}
                  className="py-2 px-4 bg-blue-600 hover:bg-blue-700 text-white font-medium rounded-lg transition duration-150 ease-in-out"
                >
                  + Create New Company
                </button>
              )}
            </div>
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

        {/* Selection Controls */}
        {filteredCompanies.length > 0 && (
          <div className="flex justify-between items-center bg-gray-50 rounded-lg mb-4">
            <div className="flex items-center">
              <input
                type="checkbox"
                className={`h-5 w-5 rounded border-gray-300 text-blue-600 focus:ring-blue-500 ${areAllCompaniesProcessing ? 'opacity-50 cursor-not-allowed' : ''
                  }`}
                checked={isAllSelected}
                onChange={handleSelectAllChange}
                disabled={areAllCompaniesProcessing}
              />
              <label htmlFor="select-all" className={`ml-2 text-sm font-medium ${areAllCompaniesProcessing ? 'text-gray-400' : 'text-gray-700'
                }`}>
                Select All
              </label>
            </div>
            {selectedCompanies.length > 0 && (
              <button
                onClick={handleProcessSelected}
                className="py-2 px-4 bg-green-600 hover:bg-green-700 text-white font-medium rounded-lg transition duration-150 ease-in-out"
              >
                Process Unsynced for Selected ({selectedCompanies.length})
              </button>
            )}
          </div>
        )}

        {filteredCompanies.length === 0 ? (
          <NoCompaniesFoundMessage searchTerm={searchTerm} />
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
                allProcessingStates={processingStates}
                isSelected={selectedCompanies.includes(company.id)}
                onSelectionChange={handleSelectionChange}
              />
            ))}
          </div>
        )}

        {/* Company Detail Modal */}
        {isModalOpen && selectedCompany && (
          <CompanyDetailModal
            isOpen={isModalOpen}
            onClose={closeCompanyModal}
            company={selectedCompany}
            qdrantData={qdrantData}
            onDeleteContract={handleDeleteContract}
            onAddContracts={handleAddContracts}
            allProcessingStates={processingStates}
            setError={setError}
          />
        )}


      </div>
    </div>
  );
}
  
export default function FileManagementPageWithLayout() {  
  return (  
    <DefaultLayout>  
      <FileManagementPage />  
    </DefaultLayout>  
  );  
} 
