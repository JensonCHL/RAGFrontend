import React from 'react';
import { ProcessingState } from '@/types';

interface ProcessingProgressDisplayProps {
  state: ProcessingState;
}

const ProcessingProgressDisplay: React.FC<ProcessingProgressDisplayProps> = ({ state }) => {
  if (state.isError) {
    return (
      <div className="bg-red-50 rounded-lg p-4 border border-red-200">
        <div className="flex justify-between items-center mb-2">
          <span className="text-sm font-medium text-red-800">
            Processing Failed: {state.currentFile}
          </span>
        </div>
        <div className="text-xs text-red-700">
          {state.errorMessage || 'An unknown error occurred'}
        </div>
      </div>
    );
  }

  return (
    <>
      <div className="flex justify-between items-center mb-2">
        <span className="text-sm font-medium text-blue-800">
          {state.currentFile 
            ? `Processing ${state.currentFile}`
            : 'Processing Documents'}
        </span>
        <span className="text-sm font-medium text-blue-800">
          {state.fileIndex || 0}/{state.totalFiles || 0}
        </span>
      </div>
      
      {state.currentFile && (
        <div className="text-xs text-blue-700 mb-2 truncate" title={state.currentFile}>
          File: {state.currentFile}
        </div>
      )}
      
      {state.currentStep && (
        <div className="text-xs text-blue-700 mb-2 capitalize">
          Step: {state.currentStep}
        </div>
      )}
      
      {state.message && (
        <div className="text-xs text-blue-700 mb-2">
          {state.message}
        </div>
      )}
      
      <div className="w-full bg-blue-200 rounded-full h-2">
        <div 
          className="bg-blue-600 h-2 rounded-full transition-all duration-300 ease-out"
          style={{ width: `${state.progress || 0}%` }}
        ></div>
      </div>
      
      {/* Detailed step progress */}
      {state.currentStep === 'ocr' && (
        <div className="mt-3">
          {state.ocrProgress ? (
            <>
              <div className="flex justify-between text-xs text-gray-600 mb-1">
                <span>OCR Progress</span>
                <span>{state.ocrProgress?.current_page || 0}/{state.ocrProgress?.total_pages || 0}</span>
              </div>
              <div className="w-full bg-gray-200 rounded-full h-1.5">
                <div 
                  className="bg-green-500 h-1.5 rounded-full transition-all duration-300 ease-out"
                  style={{ 
                    width: `${((state.ocrProgress?.current_page || 0) / (state.ocrProgress?.total_pages || 1)) * 100}%` 
                  }}
                ></div>
              </div>
            </>
          ) : (
            state.currentPage && (
              <div className="text-xs text-gray-600">
                Processing page {state.currentPage}
                {state.totalPages ? ` of ${state.totalPages}` : ''}
              </div>
            )
          )}
        </div>
      )}
      
      {state.currentStep === 'embedding' && state.embeddingProgress && (
        <div className="mt-3">
          <div className="flex justify-between text-xs text-gray-600 mb-1">
            <span>Embedding Progress</span>
            <span>{state.embeddingProgress?.batch || 0}/{state.embeddingProgress?.total_batches || 0}</span>
          </div>
          <div className="w-full bg-gray-200 rounded-full h-1.5">
            <div 
              className="bg-purple-500 h-1.5 rounded-full transition-all duration-300 ease-out"
              style={{ 
                width: `${((state.embeddingProgress?.batch || 0) / (state.embeddingProgress?.total_batches || 1)) * 100}%` 
              }}
            ></div>
          </div>
        </div>
      )}
      
      {state.currentStep === 'ingestion' && state.ingestionProgress && (
        <div className="mt-3">
          <div className="flex justify-between text-xs text-gray-600 mb-1">
            <span>Ingestion Progress</span>
            <span>{state.ingestionProgress?.points_ingested || 0}/{state.ingestionProgress?.total_points || 0}</span>
          </div>
          <div className="w-full bg-gray-200 rounded-full h-1.5">
            <div 
              className="bg-orange-500 h-1.5 rounded-full transition-all duration-300 ease-out"
              style={{ 
                width: `${((state.ingestionProgress?.points_ingested || 0) / (state.ingestionProgress?.total_points || 1)) * 100}%` 
              }}
            ></div>
          </div>
        </div>
      )}
    </>
  );
};

export default ProcessingProgressDisplay;