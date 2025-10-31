import React, { useState, useMemo } from 'react';
import { Company, QdrantCompany, ProcessingState, QdrantDocumentMetadata } from '@/types';
import ProcessingProgressDisplay from './ProcessingProgressDisplay';

interface CompanyDetailModalProps {
  isOpen: boolean;
  onClose: () => void;
  company: Company;
  qdrantData: Record<string, QdrantCompany>;
  onDeleteContract: (companyId: string, contractName: string) => void;
  onAddContracts: (companyId: string, files: File[]) => void;
  allProcessingStates: Record<string, ProcessingState>;
  setError: (message: string | null) => void;
}

const CompanyDetailModal: React.FC<CompanyDetailModalProps> = ({
  isOpen,
  onClose,
  company,
  qdrantData,
  onDeleteContract,
  onAddContracts,
  allProcessingStates,
  setError,
}) => {
  const [isModalDragging, setIsModalDragging] = useState(false);

  if (!isOpen || !company) {
    return null;
  }

  // Helper function to get deduplicated processing states for a company
  const getDeduplicatedProcessingStates = (companyId: string) => {
    // Filter processing states for the selected company that are currently active or in error
    const companyStates = Object.values(allProcessingStates)
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
    
    if (company && e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      const files = Array.from(e.dataTransfer.files);
      onAddContracts(company.id, files);
      e.dataTransfer.clearData();
    }
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

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto">
      <div className="flex items-center justify-center min-h-screen pt-4 px-4 pb-20 text-center sm:block sm:p-0">
        {/* Background overlay with blur effect */}
        <div 
          className="fixed inset-0 bg-gray-500 bg-opacity-10 backdrop-blur-sm transition-opacity duration-300 ease-out" 
          aria-hidden="true"
          onClick={onClose}
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
                  {company.name}
                </h3>
                <div className="mt-2">
                  <p className="text-sm text-gray-500">
                    {company.contracts.length} document{company.contracts.length !== 1 ? 's' : ''}
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
              onClick={() => document.getElementById(`modal-file-input-${company.id}`)?.click()}
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
                id={`modal-file-input-${company.id}`}
                type="file"
                className="hidden"
                multiple
                onChange={(e) => {
                  if (e.target.files && e.target.files.length > 0) {
                    const files = Array.from(e.target.files);
                    onAddContracts(company.id, files);
                    e.target.value = ''; // Reset input
                  }
                }}
              />
            </div>

            {/* Processing Progress Bar */}
            {company && (
              <div className="space-y-4">
                {getDeduplicatedProcessingStates(company.id).map(state => (
                  <div key={state.doc_id} className="mb-6 bg-blue-50 rounded-lg p-4 border border-blue-200">
                    <ProcessingProgressDisplay state={state} />
                  </div>
                ))}
              </div>
            )}

            {/* Documents list */}
            <div>
              <h4 className="text-md font-medium text-gray-900 mb-3">Documents</h4>
              {company.contracts.length > 0 ? (
                <div className="grid grid-cols-1 gap-3">
                  {company.contracts.map((contract) => {
                    const isSynced = qdrantData[company.name]?.documents[contract.name];
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
                              onDeleteContract(company.id, contract.name);
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
              onClick={onClose}
            >
              Close
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default CompanyDetailModal;
