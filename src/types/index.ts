export interface Contract {
  name: string;
  size: number;
  uploadDate: string;
}

export interface Company {
  id: string;
  name: string;
  contracts: Contract[];
}

export interface QdrantDocumentMetadata {
  doc_id: string;
  upload_time: string;
  pages: number[];
}

export interface QdrantCompany {
  name: string;
  documents: Record<string, QdrantDocumentMetadata>;
}

export interface ProcessingState {
  isProcessing: boolean;
  isError?: boolean;
  errorMessage?: string;
  currentFile?: string;
  currentStep?: string;
  progress?: number;
  message?: string;
  fileIndex?: number;
  totalFiles?: number;
  currentPage?: number;
  totalPages?: number;
  completedPages?: number;
  steps?: Record<string, any>;
  companyId?: string;
  doc_id: string; // Made required
  ocrProgress?: {
    current_page: number;
    total_pages: number;
  };
  embeddingProgress?: {
    batch: number;
    total_batches: number;
  };
  ingestionProgress?: {
    points_ingested: number;
    total_points: number;
  };
}

// Re-export chat types
export * from "./chat";
