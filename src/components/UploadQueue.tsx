"use client";

import { useState } from "react";
import { X, CheckCircle, AlertCircle, Loader2, XCircle } from "lucide-react";

export interface FileUploadItem {
  id: string;
  file: File;
  companyName: string;
  status: "queued" | "uploading" | "completed" | "failed";
  progress: number;
  error?: string;
}

interface UploadQueueProps {
  items: FileUploadItem[];
  onCancel: (id: string) => void;
  onRetry: (id: string) => void;
  onClearCompleted: () => void;
}

export default function UploadQueue({
  items,
  onCancel,
  onRetry,
  onClearCompleted,
}: UploadQueueProps) {
  const [isExpanded, setIsExpanded] = useState(true);

  if (items.length === 0) return null;

  const completedCount = items.filter(
    (item) => item.status === "completed"
  ).length;
  const failedCount = items.filter((item) => item.status === "failed").length;
  const uploadingCount = items.filter(
    (item) => item.status === "uploading"
  ).length;
  const queuedCount = items.filter((item) => item.status === "queued").length;

  const getStatusIcon = (status: FileUploadItem["status"]) => {
    switch (status) {
      case "completed":
        return <CheckCircle className="w-4 h-4 text-green-600" />;
      case "failed":
        return <AlertCircle className="w-4 h-4 text-red-600" />;
      case "uploading":
        return <Loader2 className="w-4 h-4 text-blue-600 animate-spin" />;
      case "queued":
        return (
          <div className="w-4 h-4 rounded-full border-2 border-gray-400" />
        );
    }
  };

  const getStatusColor = (status: FileUploadItem["status"]) => {
    switch (status) {
      case "completed":
        return "bg-green-50 dark:bg-green-900/20 border-green-200 dark:border-green-800";
      case "failed":
        return "bg-red-50 dark:bg-red-900/20 border-red-200 dark:border-red-800";
      case "uploading":
        return "bg-blue-50 dark:bg-blue-900/20 border-blue-200 dark:border-blue-800";
      case "queued":
        return "bg-gray-50 dark:bg-gray-800 border-gray-200 dark:border-gray-700";
    }
  };

  return (
    <div className="bg-white dark:bg-gray-800 rounded-lg shadow-md border border-gray-200 dark:border-gray-700 mb-6 transition-colors">
      {/* Header */}
      <div
        className="px-6 py-4 flex items-center justify-between cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
        onClick={() => setIsExpanded(!isExpanded)}
      >
        <div className="flex items-center gap-3">
          <div className="text-2xl">📤</div>
          <div>
            <h3 className="font-semibold text-gray-900 dark:text-white">
              Upload Queue
            </h3>
            <p className="text-sm text-gray-600 dark:text-gray-400">
              {completedCount} of {items.length} completed
              {failedCount > 0 && (
                <span className="text-red-600 dark:text-red-400 ml-2">
                  • {failedCount} failed
                </span>
              )}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          {completedCount > 0 && (
            <button
              onClick={(e) => {
                e.stopPropagation();
                onClearCompleted();
              }}
              className="text-sm text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white"
            >
              Clear completed
            </button>
          )}
          <button className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300">
            {isExpanded ? "▼" : "▶"}
          </button>
        </div>
      </div>

      {/* Queue Items */}
      {isExpanded && (
        <div className="px-6 pb-4 space-y-2 max-h-96 overflow-y-auto">
          {items.map((item) => (
            <div
              key={item.id}
              className={`rounded-lg border p-3 transition-colors ${getStatusColor(
                item.status
              )}`}
            >
              <div className="flex items-start justify-between gap-3">
                <div className="flex items-start gap-3 flex-1 min-w-0">
                  {getStatusIcon(item.status)}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <p className="text-sm font-medium text-gray-900 dark:text-white truncate">
                        {item.file.name}
                      </p>
                      <span className="text-xs text-gray-500 dark:text-gray-400 whitespace-nowrap">
                        {(item.file.size / 1024 / 1024).toFixed(2)} MB
                      </span>
                    </div>
                    <p className="text-xs text-gray-600 dark:text-gray-400 mt-1">
                      {item.companyName}
                    </p>

                    {/* Progress Bar */}
                    {item.status === "uploading" && (
                      <div className="mt-2">
                        <div className="flex justify-between text-xs text-gray-600 dark:text-gray-400 mb-1">
                          <span>Uploading...</span>
                          <span>{item.progress}%</span>
                        </div>
                        <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-1.5">
                          <div
                            className="bg-blue-600 h-1.5 rounded-full transition-all duration-300"
                            style={{ width: `${item.progress}%` }}
                          />
                        </div>
                      </div>
                    )}

                    {/* Error Message */}
                    {item.status === "failed" && item.error && (
                      <p className="text-xs text-red-600 dark:text-red-400 mt-1">
                        {item.error}
                      </p>
                    )}
                  </div>
                </div>

                {/* Action Buttons */}
                <div className="flex items-center gap-2">
                  {item.status === "failed" && (
                    <button
                      onClick={() => onRetry(item.id)}
                      className="text-xs px-2 py-1 bg-blue-600 text-white rounded hover:bg-blue-700 transition-colors"
                    >
                      Retry
                    </button>
                  )}
                  {(item.status === "queued" || item.status === "failed") && (
                    <button
                      onClick={() => onCancel(item.id)}
                      className="text-gray-400 hover:text-red-600 dark:hover:text-red-400 transition-colors"
                    >
                      <XCircle className="w-4 h-4" />
                    </button>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Summary Footer */}
      {isExpanded && (
        <div className="px-6 py-3 border-t border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-900/50 rounded-b-lg">
          <div className="flex items-center justify-between text-xs text-gray-600 dark:text-gray-400">
            <div className="flex items-center gap-4">
              <span>✓ {completedCount} completed</span>
              {uploadingCount > 0 && <span>⏫ {uploadingCount} uploading</span>}
              {queuedCount > 0 && <span>⏳ {queuedCount} queued</span>}
              {failedCount > 0 && (
                <span className="text-red-600">❌ {failedCount} failed</span>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
