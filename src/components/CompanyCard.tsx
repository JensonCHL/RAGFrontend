'use client';

import { useState, useMemo } from 'react';
import { Contract, Company, QdrantDocumentMetadata, QdrantCompany, ProcessingState } from '@/types';

interface CompanyCardProps {
  company: Company;
  qdrantData: QdrantCompany | null;
  onDelete: (companyId: string) => void;
  onDeleteContract: (companyId: string, contractName: string) => void;
  onAddContracts: (companyId: string, files: File[]) => void;
  onProcessUnsynced: (companyId: string) => void;
  onOpenModal: (company: Company) => void;
  allProcessingStates: Record<string, ProcessingState>; // Changed to receive all states
}

export default function CompanyCard({
  company,
  qdrantData,
  onDelete,
  onDeleteContract,
  onAddContracts,
  onProcessUnsynced,
  onOpenModal,
  allProcessingStates
}: CompanyCardProps) {
  const [isDragging, setIsDragging] = useState(false);

  // Filter processing states relevant to this company
  const companyProcessingStates = useMemo(() => {
    return Object.values(allProcessingStates).filter(
      (state) => state.companyId === company.id
    );
  }, [allProcessingStates, company.id]);

  // Determine if any document in this company is currently processing
  const isAnyDocumentProcessing = useMemo(() => {
    return companyProcessingStates.some((state) => state.isProcessing);
  }, [companyProcessingStates]);

  // Determine if any document in this company has an error
  const isAnyDocumentInError = useMemo(() => {
    return companyProcessingStates.some((state) => state.isError);
  }, [companyProcessingStates]);
  const formatFileSize = (bytes: number): string => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  const formatDate = (dateString: string): string => {
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      timeZone: 'UTC'
    });
  };

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

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
    
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      const files = Array.from(e.dataTransfer.files);
      onAddContracts(company.id, files);
      e.dataTransfer.clearData();
    }
  };

  const handleFileInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      const files = Array.from(e.target.files);
      onAddContracts(company.id, files);
      e.target.value = ''; // Reset input
    }
  };

  // Calculate synchronization status
  const getSyncStatus = () => {
    if (!qdrantData) {
      // Company not found in Qdrant
      return {
        syncedCount: 0,
        totalCount: company.contracts.length,
        isSynced: false,
        hasUnsynced: company.contracts.length > 0
      };
    }
    
    const syncedDocs = Object.keys(qdrantData.documents);
    const totalDocs = company.contracts.length;
    const syncedCount = company.contracts.filter(contract => 
      syncedDocs.includes(contract.name)
    ).length;
    
    return {
      syncedCount,
      totalCount: totalDocs,
      isSynced: syncedCount === totalDocs && totalDocs > 0,
      hasUnsynced: syncedCount < totalDocs
    };
  };

  const syncStatus = getSyncStatus();

  return (
    <div className="bg-white rounded-lg shadow overflow-hidden">
      {/* Company Header - Windows File Manager Style */}
      <div 
        className="p-4 border-b border-gray-200 cursor-pointer hover:bg-gray-50"
        onClick={(e) => {
          e.stopPropagation();
          onOpenModal(company);
        }}
        onDragEnter={handleDragEnter}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
      >
        <div className="flex items-start w-full flex-nowrap">
          <div className="flex-shrink-0 w-10 h-10 bg-blue-100 rounded-md flex items-center justify-center">
            <svg 
              className="w-6 h-6 text-blue-600" 
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
          <div className="ml-3 flex-grow min-w-0 w-3/4">
            <h3 className="text-sm font-medium text-gray-900 truncate w-full">{company.name}</h3>
            <div className="flex flex-wrap items-center mt-1 gap-2 w-full">
              <span className="text-xs text-gray-500 truncate">
                {company.contracts.length} item{company.contracts.length !== 1 ? 's' : ''}
              </span>
              <span className="text-gray-300">•</span>
              <span className="text-xs text-gray-500 truncate">
                {syncStatus.syncedCount}/{syncStatus.totalCount} processed
              </span>
            </div>
          </div>
          <div className="flex items-center ml-2 flex-shrink-0">
            {isAnyDocumentProcessing ? (
              <div className="flex items-center">
                <div className="flex flex-col">
                  <div className="flex items-center">
                    {isAnyDocumentInError ? (
                      <>
                        <div className="w-3 h-3 rounded-full bg-red-500 mr-2"></div>
                        <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-800">
                          Error
                        </span>
                      </>
                    ) : (
                      <>
                        <div className="w-3 h-3 rounded-full bg-blue-500 animate-pulse mr-2"></div>
                        <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
                          Processing...
                        </span>
                      </>
                    )}
                  </div>
                  {isAnyDocumentInError ? (
                    <span className="text-xs text-red-500 truncate max-w-[120px]" title={companyProcessingStates.find(s => s.isError)?.errorMessage}>
                      {companyProcessingStates.find(s => s.isError)?.errorMessage}
                    </span>
                  ) : (
                    <span className="text-xs text-gray-500 truncate max-w-[120px]">
                      {companyProcessingStates.filter(s => s.isProcessing).length} file(s) processing
                    </span>
                  )}
                </div>
              </div>
            ) : syncStatus.hasUnsynced ? (
              <div className="flex items-center">
                <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-800 mr-2">
                  Not Sync
                </span>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    onProcessUnsynced(company.id);
                  }}
                  className="p-1 text-blue-600 hover:text-blue-800"
                  title="Process unsynced documents"
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
                      d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
                    ></path>
                  </svg>
                </button>
              </div>
            ) : syncStatus.isSynced && syncStatus.totalCount > 0 ? (
              <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">
                Synced
              </span>
            ) : (
              <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-800">
                Empty
              </span>
            )}
            <button
              onClick={(e) => {
                e.stopPropagation();
                onDelete(company.id);
              }}
              className="ml-2 p-1 text-gray-400 hover:text-red-500"
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
      </div>

      {/* Contracts Grid - Windows File Manager Style */}
      <div 
        className={`p-3 ${isDragging ? 'bg-blue-50 border-2 border-dashed border-blue-300 rounded' : ''}`}
        onDragEnter={handleDragEnter}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
      >
        {company.contracts.length > 0 ? (
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-2">
            {company.contracts.map((contract) => {
              const isSynced = qdrantData && qdrantData.documents[contract.name];
              const contractProcessingState = companyProcessingStates.find(
                (state) => state.currentFile === contract.name
              );

              return (
                <div 
                  key={contract.name} 
                  className="group relative p-2 rounded hover:bg-gray-100"
                >
                  <div className="flex flex-col items-center">
                    <div className="w-12 h-12 flex items-center justify-center">
                      {contract.name.toLowerCase().endsWith('.pdf') ? (
                        <div className="w-8 h-10 bg-red-100 rounded flex items-center justify-center">
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
                      ) : (
                        <div className="w-8 h-10 bg-gray-100 rounded flex items-center justify-center">
                          <svg 
                            className="w-4 h-4 text-gray-600" 
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
                      )}
                    </div>
                    <div className="mt-1 text-center w-full">
                      <p className="text-xs text-gray-900 truncate px-1" title={contract.name}>
                        {contract.name}
                      </p>
                      <p className="text-xs text-gray-500 mt-0.5 truncate">
                        {formatFileSize(contract.size)}
                      </p>
                    </div>
                    {contractProcessingState?.isProcessing ? (
                      <div className="absolute top-0 right-0 w-3 h-3 bg-blue-500 rounded-full animate-pulse" title="Processing"></div>
                    ) : contractProcessingState?.isError ? (
                      <div className="absolute top-0 right-0 w-3 h-3 bg-red-500 rounded-full" title={`Error: ${contractProcessingState.errorMessage}`}></div>
                    ) : isSynced ? (
                      <div className="absolute top-0 right-0 w-3 h-3 bg-green-500 rounded-full" title="Processed"></div>
                    ) : null}
                  </div>
                  
                  {/* Delete button on hover */}
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      onDeleteContract(company.id, contract.name);
                    }}
                    className="absolute top-0 left-0 p-1 text-gray-400 hover:text-red-500 opacity-0 group-hover:opacity-100 transition-opacity"
                  >
                    <svg 
                      className="w-3 h-3" 
                      fill="none" 
                      stroke="currentColor" 
                      viewBox="0 0 24 24" 
                      xmlns="http://www.w3.org/2000/svg"
                    >
                      <path 
                        strokeLinecap="round" 
                        strokeLinejoin="round" 
                        strokeWidth="2" 
                        d="M6 18L18 6M6 6l12 12"
                      ></path>
                    </svg>
                  </button>
                </div>
              );
            })}
          </div>
        ) : (
          <div className="text-center py-6">
            <svg 
              className="mx-auto h-8 w-8 text-gray-400" 
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
            <p className="mt-2 text-sm text-gray-500">No files in this folder</p>
          </div>
        )}
        
        {/* Hidden file input for drag and drop */}
        <input
          id={`file-input-${company.id}`}
          type="file"
          className="hidden"
          multiple
          onChange={handleFileInput}
        />
      </div>
    </div>
  );
}