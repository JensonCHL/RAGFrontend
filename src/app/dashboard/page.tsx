'use client';

import { useState, useEffect, useMemo } from 'react';
import Link from 'next/link';
import { ProcessingState } from '@/types';
import ProcessingProgressDisplay from '@/components/ProcessingProgressDisplay';

// Interface for document metadata
interface DocumentMetadata {
  doc_id: string;
  upload_time: string;
  pages: number[];
}

// Interface for Qdrant data
interface QdrantCompany {
  name: string;
  documents: Record<string, DocumentMetadata>;
  isExpanded?: boolean;
}

export default function DashboardPage() {
  const [qdrantCompanies, setQdrantCompanies] = useState<QdrantCompany[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [deleting, setDeleting] = useState<{company?: string, document?: string}>({});
  const [searchTerm, setSearchTerm] = useState('');
  const [showProcessingStates, setShowProcessingStates] = useState(true); // Define showProcessingStates
  const [processingStates, setProcessingStates] = useState<ProcessingState[]>([]);
  const [selectedItems, setSelectedItems] = useState<Record<string, boolean>>({}); // For bulk selection
  const [isSelecting, setIsSelecting] = useState(false); // Toggle selection mode

  // Fetch all Qdrant data on page load
  useEffect(() => {
    fetchQdrantData();
    
    // Set up SSE for real-time processing updates
    let eventSource: EventSource | null = null;
    
    // Only set up SSE if we're showing processing states
    if (showProcessingStates) {
      const setupEventSource = () => {
        eventSource = new EventSource('http://localhost:5000/events/processing-updates');
        
        eventSource.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data);
            
            // Handle different types of messages
            if (data.type === 'states_updated') {
              // Refresh Qdrant data when processing states change
              fetchQdrantData();
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
    }
    
    // Cleanup function
    return () => {
      if (eventSource) {
        eventSource.close();
      }
    };
  }, [showProcessingStates]);

  // Fetch all Qdrant data upfront with the new efficient endpoint
  const fetchQdrantData = async () => {
    try {
      setLoading(true);
      setError(null);
      
      // Single call to get all companies with their documents
      const response = await fetch('http://localhost:5000/api/companies-with-documents');
      const data = await response.json();
      
      if (data.success) {
        // Transform the data into our component format
        const companiesWithDocuments: QdrantCompany[] = Object.entries(data.data).map(([name, documents]) => ({
          name,
          documents: documents as Record<string, DocumentMetadata>,
          isExpanded: false
        }));
        
        setQdrantCompanies(companiesWithDocuments);
      } else {
        setError(data.error || 'Failed to fetch companies with documents from Qdrant');
      }
    } catch (err) {
      setError('Failed to connect to the Qdrant backend service. Make sure the Flask API is running.');
      console.error('Error fetching Qdrant data:', err);
    } finally {
      setLoading(false);
    }
  };

  // Calculate summary statistics
  const summaryStats = useMemo(() => {
    let totalDocuments = 0;
    let totalFiles = 0;
    let totalPages = 0;
    
    qdrantCompanies.forEach(company => {
      const documentCount = Object.keys(company.documents).length;
      totalDocuments += documentCount;
      totalFiles += documentCount;
      
      Object.values(company.documents).forEach(doc => {
        totalPages += doc.pages.length;
      });
    });
    
    return { totalDocuments, totalFiles, totalPages };
  }, [qdrantCompanies]);

  // Filter companies based on search term
  const filteredCompanies = useMemo(() => {
    if (!searchTerm.trim()) {
      return qdrantCompanies;
    }
    
    const term = searchTerm.toLowerCase();
    return qdrantCompanies
      .map(company => {
        // Check if company name matches
        const companyNameMatch = company.name.toLowerCase().includes(term);
        
        // Check if any document name matches
        const matchingDocuments: Record<string, DocumentMetadata> = {};
        Object.entries(company.documents).forEach(([docName, docMeta]) => {
          if (docName.toLowerCase().includes(term)) {
            matchingDocuments[docName] = docMeta;
          }
        });
        
        // If company name matches or there are matching documents, include in results
        if (companyNameMatch || Object.keys(matchingDocuments).length > 0) {
          return {
            ...company,
            documents: companyNameMatch ? company.documents : matchingDocuments
          };
        }
        
        return null;
      })
      .filter(company => company !== null) as QdrantCompany[];
  }, [qdrantCompanies, searchTerm]);

  const toggleCompany = (companyName: string) => {
    setQdrantCompanies(prev => 
      prev.map(company => 
        company.name === companyName 
          ? { ...company, isExpanded: !company.isExpanded } 
          : company
      )
    );
  };

  const deleteCompany = async (companyName: string) => {
    if (!confirm(`Are you sure you want to delete all data for company "${companyName}"? This action cannot be undone.`)) {
      return;
    }

    try {
      setDeleting({ company: companyName });
      
      const response = await fetch(`http://localhost:5000/api/companies/${companyName}`, {
        method: 'DELETE',
      });
      
      const data = await response.json();
      
      if (data.success) {
        // Remove company from state
        setQdrantCompanies(prev => prev.filter(company => company.name !== companyName));
        alert(`Successfully deleted company "${companyName}" and all its documents.`);
      } else {
        alert(`Failed to delete company: ${data.error}`);
      }
    } catch (err) {
      console.error('Error deleting company:', err);
      alert('Failed to delete company. Please try again.');
    } finally {
      setDeleting({});
    }
  };

  const deleteDocument = async (companyName: string, documentName: string) => {
    if (!confirm(`Are you sure you want to delete document "${documentName}"? This action cannot be undone.`)) {
      return;
    }

    try {
      setDeleting({ company: companyName, document: documentName });
      
      const response = await fetch(`http://localhost:5000/api/companies/${companyName}/documents/${encodeURIComponent(documentName)}`, {
        method: 'DELETE',
      });
      
      const data = await response.json();
      
      if (data.success) {
        // Remove document from state
        setQdrantCompanies(prev => 
          prev.map(company => 
            company.name === companyName 
              ? { 
                  ...company, 
                  documents: Object.fromEntries(
                    Object.entries(company.documents).filter(([name]) => name !== documentName)
                  )
                } 
              : company
          )
        );
        alert(`Successfully deleted document "${documentName}".`);
      } else {
        alert(`Failed to delete document: ${data.error}`);
      }
    } catch (err) {
      console.error('Error deleting document:', err);
      alert('Failed to delete document. Please try again.');
    } finally {
      setDeleting({});
    }
  };

  // Bulk delete functions
  const toggleSelection = (key: string) => {
    setSelectedItems(prev => ({
      ...prev,
      [key]: !prev[key]
    }));
  };

  const selectAll = () => {
    const newSelectedItems: Record<string, boolean> = {};
    filteredCompanies.forEach(company => {
      // Select company
      newSelectedItems[`company:${company.name}`] = true;
      // Select all documents in expanded companies
      if (company.isExpanded) {
        Object.keys(company.documents).forEach(docName => {
          newSelectedItems[`document:${company.name}:${docName}`] = true;
        });
      }
    });
    setSelectedItems(newSelectedItems);
  };

  const clearSelection = () => {
    setSelectedItems({});
  };

  const bulkDelete = async () => {
    const selectedCompanies = Object.keys(selectedItems)
      .filter(key => key.startsWith('company:') && selectedItems[key])
      .map(key => key.split(':')[1]);
    
    const selectedDocuments = Object.keys(selectedItems)
      .filter(key => key.startsWith('document:') && selectedItems[key])
      .map(key => {
        const [, company, document] = key.split(':');
        return { company, document };
      });

    if (selectedCompanies.length === 0 && selectedDocuments.length === 0) {
      alert('Please select at least one item to delete.');
      return;
    }

    const message = `Are you sure you want to delete ${selectedCompanies.length} companies and ${selectedDocuments.length} documents? This action cannot be undone.`;
    if (!confirm(message)) {
      return;
    }

    try {
      setDeleting({});

      // Delete companies
      for (const companyName of selectedCompanies) {
        setDeleting({ company: companyName });
        const response = await fetch(`http://localhost:5000/api/companies/${companyName}`, {
          method: 'DELETE',
        });
        
        const data = await response.json();
        
        if (data.success) {
          setQdrantCompanies(prev => prev.filter(company => company.name !== companyName));
        } else {
          alert(`Failed to delete company "${companyName}": ${data.error}`);
        }
      }

      // Delete documents
      for (const { company, document } of selectedDocuments) {
        setDeleting({ company, document });
        const response = await fetch(`http://localhost:5000/api/companies/${company}/documents/${encodeURIComponent(document)}`, {
          method: 'DELETE',
        });
        
        const data = await response.json();
        
        if (data.success) {
          setQdrantCompanies(prev => 
            prev.map(comp => 
              comp.name === company 
                ? { 
                    ...comp, 
                    documents: Object.fromEntries(
                      Object.entries(comp.documents).filter(([name]) => name !== document)
                    )
                  } 
                : comp
            )
          );
        } else {
          alert(`Failed to delete document "${document}": ${data.error}`);
        }
      }

      alert('Bulk deletion completed.');
      clearSelection();
    } catch (err) {
      console.error('Error during bulk deletion:', err);
      alert('Failed to complete bulk deletion. Please try again.');
    } finally {
      setDeleting({});
    }
  };

  // Format upload time for display
  const formatUploadTime = (uploadTime: string) => {
    try {
      return new Date(uploadTime).toLocaleString();
    } catch {
      return uploadTime;
    }
  };

  // Format pages for display
  const formatPages = (pages: number[]) => {
    if (pages.length === 0) return 'N/A';
    if (pages.length === 1) return `Page ${pages[0]}`;
    
    // Show range if consecutive
    const sorted = [...pages].sort((a, b) => a - b);
    const min = sorted[0];
    const max = sorted[sorted.length - 1];
    
    if (max - min === sorted.length - 1) {
      return `${min}-${max}`;
    }
    
    return `${pages.length} pages`;
  };

  return (
    <div className="min-h-screen bg-gray-50 p-8">
      <div className="max-w-4xl mx-auto">
        <header className="mb-8">
          <div className="flex justify-between items-center">
            <div>
              <h1 className="text-3xl font-bold text-gray-900">Document Processing Dashboard</h1>
              <p className="text-gray-600 mt-2">
                View processed documents and manage your ingestion workflow
              </p>
            </div>
            <Link 
              href="/file-management"
              className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
            >
              <svg className="mr-2 -ml-1 h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"></path>
              </svg>
              File Management
            </Link>
          </div>
        </header>

        {/* Summary Statistics */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
          <div className="bg-white rounded-lg shadow p-6">
            <div className="flex items-center">
              <div className="rounded-full bg-blue-100 p-3">
                <svg className="w-6 h-6 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4"></path>
                </svg>
              </div>
              <div className="ml-4">
                <h3 className="text-sm font-medium text-gray-500">Total Companies</h3>
                <p className="text-2xl font-semibold text-gray-900">{qdrantCompanies.length}</p>
              </div>
            </div>
          </div>
          
          <div className="bg-white rounded-lg shadow p-6">
            <div className="flex items-center">
              <div className="rounded-full bg-green-100 p-3">
                <svg className="w-6 h-6 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path>
                </svg>
              </div>
              <div className="ml-4">
                <h3 className="text-sm font-medium text-gray-500">Total Documents</h3>
                <p className="text-2xl font-semibold text-gray-900">{summaryStats.totalDocuments}</p>
              </div>
            </div>
          </div>
          
          <div className="bg-white rounded-lg shadow p-6">
            <div className="flex items-center">
              <div className="rounded-full bg-purple-100 p-3">
                <svg className="w-6 h-6 text-purple-600" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M7 4v16M17 4v16M3 8h4m10 0h4M3 12h18M3 16h4m10 0h4M4 20h16a1 1 0 001-1V5a1 1 0 00-1-1H4a1 1 0 00-1 1v14a1 1 0 001 1z"></path>
                </svg>
              </div>
              <div className="ml-4">
                <h3 className="text-sm font-medium text-gray-500">Total Pages</h3>
                <p className="text-2xl font-semibold text-gray-900">{summaryStats.totalPages}</p>
              </div>
            </div>
          </div>
        </div>

        {/* Search and Controls */}
        <div className="mb-6">
          <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
            <div className="relative flex-grow max-w-md">
              <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                <svg className="h-5 w-5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"></path>
                </svg>
              </div>
              <input
                type="text"
                className="block w-full pl-10 pr-3 py-2 border border-gray-300 rounded-md leading-5 bg-white placeholder-gray-500 focus:outline-none focus:placeholder-gray-400 focus:ring-1 focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
                placeholder="Search companies or documents..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
              />
            </div>
            <div className="flex space-x-2">
              <button 
                onClick={() => setIsSelecting(!isSelecting)}
                className={`inline-flex items-center px-4 py-2 border text-sm font-medium rounded-md focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 ${
                  isSelecting 
                    ? 'border-blue-300 text-blue-700 bg-blue-50 hover:bg-blue-100' 
                    : 'border-gray-300 text-gray-700 bg-white hover:bg-gray-50'
                }`}
              >
                <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"></path>
                </svg>
                {isSelecting ? 'Cancel Selection' : 'Select Items'}
              </button>
              {isSelecting && (
                <>
                  <button 
                    onClick={selectAll}
                    className="inline-flex items-center px-4 py-2 border border-gray-300 text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
                  >
                    Select All
                  </button>
                  <button 
                    onClick={bulkDelete}
                    disabled={Object.values(selectedItems).filter(Boolean).length === 0}
                    className={`inline-flex items-center px-4 py-2 border text-sm font-medium rounded-md focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-red-500 ${
                      Object.values(selectedItems).filter(Boolean).length === 0
                        ? 'border-gray-300 text-gray-400 bg-gray-100 cursor-not-allowed'
                        : 'border-red-300 text-red-700 bg-red-50 hover:bg-red-100'
                    }`}
                  >
                    <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"></path>
                    </svg>
                    Delete Selected
                  </button>
                </>
              )}
              <button 
                onClick={fetchQdrantData}
                className="inline-flex items-center px-4 py-2 border border-gray-300 text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
              >
                <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"></path>
                </svg>
                Refresh
              </button>
            </div>
          </div>
        </div>

        {/* Main Content - Processed Documents from Qdrant */}
        <div className="mb-8">
          <h2 className="text-2xl font-bold text-gray-800 mb-6">Processed Documents</h2>

          {loading ? (
            <div className="bg-white rounded-lg shadow p-8 flex justify-center items-center">
              <div className="text-center">
                <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
                <p className="mt-4 text-gray-600">Loading processed documents...</p>
              </div>
            </div>
          ) : error ? (
            <div className="bg-white rounded-lg shadow p-6">
              <div className="bg-red-50 border border-red-200 rounded-md p-4">
                <div className="flex">
                  <div className="flex-shrink-0">
                    <svg className="h-5 w-5 text-red-400" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor">
                      <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
                    </svg>
                  </div>
                  <div className="ml-3">
                    <h3 className="text-sm font-medium text-red-800">Error Loading Data</h3>
                    <div className="mt-2 text-sm text-red-700">
                      <p>{error}</p>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          ) : filteredCompanies.length === 0 ? (
            <div className="bg-white rounded-lg shadow p-8 text-center">
              <svg className="mx-auto h-16 w-16 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
              <h3 className="mt-4 text-lg font-medium text-gray-900">
                {searchTerm ? 'No matching documents found' : 'No processed documents found'}
              </h3>
              <p className="mt-2 text-gray-500">
                {searchTerm 
                  ? `No companies or documents match your search for "${searchTerm}". Try a different search term.`
                  : 'Documents will appear here after they have been processed by the ingestion pipeline.'}
              </p>
              {!searchTerm && (
                <div className="mt-6">
                  <Link 
                    href="/file-management"
                    className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
                  >
                    Upload Documents
                  </Link>
                </div>
              )}
            </div>
          ) : (
            <div className="space-y-4">
              {filteredCompanies.map((company) => (
                <div key={company.name} className="bg-white rounded-lg shadow overflow-hidden">
                  <div className="p-6">
                    <div className="flex justify-between items-center">
                      <div className="flex items-center flex-grow">
                        {isSelecting && (
                          <input
                            type="checkbox"
                            checked={!!selectedItems[`company:${company.name}`]}
                            onChange={() => toggleSelection(`company:${company.name}`)}
                            className="h-4 w-4 text-blue-600 rounded border-gray-300 focus:ring-blue-500 mr-3"
                          />
                        )}
                        <div 
                          className="flex items-center cursor-pointer flex-grow"
                          onClick={() => toggleCompany(company.name)}
                        >
                          <svg 
                            className={`w-5 h-5 text-gray-400 mr-3 transform transition-transform duration-200 ${company.isExpanded ? 'rotate-90' : ''}`} 
                            fill="none" 
                            stroke="currentColor" 
                            viewBox="0 0 24 24" 
                            xmlns="http://www.w3.org/2000/svg"
                          >
                            <path 
                              strokeLinecap="round" 
                              strokeLinejoin="round" 
                              strokeWidth="2" 
                              d="M9 5l7 7-7 7"
                            ></path>
                          </svg>
                          <h3 className="text-lg font-semibold text-gray-900">{company.name}</h3>
                        </div>
                      </div>
                      <div className="flex items-center space-x-2">
                        <span className="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-blue-100 text-blue-800">
                          {Object.keys(company.documents).length} {Object.keys(company.documents).length === 1 ? 'document' : 'documents'}
                        </span>
                        {!isSelecting && (
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              deleteCompany(company.name);
                            }}
                            disabled={deleting.company === company.name}
                            className={`p-2 rounded-full ${deleting.company === company.name ? 'bg-gray-200' : 'bg-red-100 hover:bg-red-200'} text-red-600 transition-colors duration-150`}
                            title="Delete company and all its documents"
                          >
                            {deleting.company === company.name ? (
                              <svg className="w-4 h-4 animate-spin" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"></path>
                              </svg>
                            ) : (
                              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"></path>
                              </svg>
                            )}
                          </button>
                        )}
                      </div>
                    </div>
                  </div>
                  
                  {company.isExpanded && (
                    <div className="px-6 pb-6">
                      {Object.keys(company.documents).length > 0 ? (
                        <ul className="mt-2 space-y-3">
                          {Object.entries(company.documents).map(([documentName, metadata]) => (
                            <li key={documentName} className="flex items-start py-3 border-b border-gray-100 last:border-0">
                              {isSelecting && (
                                <input
                                  type="checkbox"
                                  checked={!!selectedItems[`document:${company.name}:${documentName}`]}
                                  onChange={() => toggleSelection(`document:${company.name}:${documentName}`)}
                                  className="h-4 w-4 text-blue-600 rounded border-gray-300 focus:ring-blue-500 mt-1 mr-3"
                                />
                              )}
                              <div className="flex-shrink-0 mt-1">
                                <svg className="h-5 w-5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path>
                                </svg>
                              </div>
                              <div className="ml-3 flex-grow">
                                <p className="text-sm font-medium text-gray-900 break-words">{documentName}</p>
                                <div className="mt-1 text-xs text-gray-500 space-y-1">
                                  <div className="flex items-center">
                                    <span className="inline-block w-20">Doc ID:</span>
                                    <span className="font-mono text-xs">{metadata.doc_id}</span>
                                  </div>
                                  <div className="flex items-center">
                                    <span className="inline-block w-20">Uploaded:</span>
                                    <span>{formatUploadTime(metadata.upload_time)}</span>
                                  </div>
                                  <div className="flex items-center">
                                    <span className="inline-block w-20">Pages:</span>
                                    <span>{formatPages(metadata.pages)}</span>
                                  </div>
                                </div>
                              </div>
                              {!isSelecting && (
                                <button
                                  onClick={() => deleteDocument(company.name, documentName)}
                                  disabled={deleting.document === documentName && deleting.company === company.name}
                                  className={`ml-2 p-1.5 rounded-full ${deleting.document === documentName && deleting.company === company.name ? 'bg-gray-200' : 'bg-red-100 hover:bg-red-200'} text-red-600 transition-colors duration-150`}
                                  title="Delete document"
                                >
                                  {deleting.document === documentName && deleting.company === company.name ? (
                                    <svg className="w-4 h-4 animate-spin" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"></path>
                                    </svg>
                                  ) : (
                                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"></path>
                                    </svg>
                                  )}
                                </button>
                              )}
                            </li>
                          ))}
                        </ul>
                      ) : (
                        <div className="mt-4 text-center py-4">
                          <p className="text-sm text-gray-500">No documents match your search</p>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}