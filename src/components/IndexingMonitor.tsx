"use client";

import { useState } from "react";
import { ChevronDown, ChevronUp, Activity, FileText } from "lucide-react";

interface IndexingJob {
  job_id: string;
  index_name: string;
  status: string;
  total_documents: number;
  processed_documents: number;
  queued_documents: number;
  start_time?: number;
}

interface IndexingQueueStatus {
  success: boolean;
  active_jobs: number;
  max_jobs: number;
  available_slots: number;
  jobs: IndexingJob[];
}

interface IndexingMonitorProps {
  queueStatus: IndexingQueueStatus | null;
}

export default function IndexingMonitor({ queueStatus }: IndexingMonitorProps) {
  const [isExpanded, setIsExpanded] = useState(false);

  const hasActiveJobs = queueStatus && queueStatus.active_jobs > 0;
  const utilizationPercent = queueStatus
    ? ((queueStatus.active_jobs / queueStatus.max_jobs) * 100).toFixed(0)
    : 0;

  return (
    <div className="bg-white dark:bg-gray-800 rounded-lg shadow-md border border-gray-200 dark:border-gray-700 mb-6 transition-colors duration-300">
      {/* Header - Always Visible */}
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full px-6 py-4 flex items-center justify-between hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
      >
        <div className="flex items-center gap-4">
          <Activity
            className={`w-5 h-5 ${
              hasActiveJobs
                ? "text-blue-600 dark:text-blue-400 animate-pulse"
                : "text-gray-400 dark:text-gray-500"
            }`}
          />
          <div className="text-left">
            <h3 className="font-semibold text-gray-900 dark:text-white">
              Indexing Monitor
            </h3>
            <p className="text-sm text-gray-600 dark:text-gray-400">
              {hasActiveJobs ? (
                <>
                  <span className="font-medium text-blue-600 dark:text-blue-400">
                    {queueStatus?.active_jobs}/{queueStatus?.max_jobs}
                  </span>{" "}
                  jobs active
                  {queueStatus?.available_slots === 0 && (
                    <span className="ml-2 text-orange-600 dark:text-orange-400">
                      • Capacity full
                    </span>
                  )}
                </>
              ) : (
                <span className="text-gray-500 dark:text-gray-400">
                  No active indexing jobs
                </span>
              )}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-4">
          {hasActiveJobs && (
            <div className="text-right">
              <div className="text-sm font-medium text-gray-900 dark:text-white">
                {utilizationPercent}% Utilized
              </div>
              <div className="text-xs text-gray-500 dark:text-gray-400">
                {queueStatus?.available_slots} slot
                {queueStatus?.available_slots !== 1 ? "s" : ""} available
              </div>
            </div>
          )}
          {isExpanded ? (
            <ChevronUp className="w-5 h-5 text-gray-400" />
          ) : (
            <ChevronDown className="w-5 h-5 text-gray-400" />
          )}
        </div>
      </button>

      {/* Expanded Content */}
      {isExpanded && hasActiveJobs && (
        <div className="px-6 pb-6 space-y-4 border-t border-gray-200 dark:border-gray-700 pt-4">
          {/* Active Jobs */}
          {queueStatus?.jobs.map((job) => (
            <div
              key={job.job_id}
              className="bg-gray-50 dark:bg-gray-900 rounded-lg p-4 space-y-3"
            >
              {/* Job Header */}
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <FileText className="w-4 h-4 text-blue-600 dark:text-blue-400" />
                  <span className="font-medium text-gray-900 dark:text-white">
                    {job.index_name}
                  </span>
                  <span
                    className={`px-2 py-0.5 text-xs rounded-full ${
                      job.status === "processing"
                        ? "bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300"
                        : job.status === "completed"
                        ? "bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300"
                        : "bg-gray-100 text-gray-700 dark:bg-gray-700 dark:text-gray-300"
                    }`}
                  >
                    {job.status}
                  </span>
                </div>
                <div className="text-sm text-gray-600 dark:text-gray-400">
                  {job.processed_documents}/{job.total_documents} documents
                </div>
              </div>

              {/* Progress Bar */}
              <div className="space-y-1">
                <div className="flex justify-between text-xs text-gray-600 dark:text-gray-400">
                  <span>Progress</span>
                  <span>
                    {job.total_documents > 0
                      ? Math.round(
                          (job.processed_documents / job.total_documents) * 100
                        )
                      : 0}
                    %
                  </span>
                </div>
                <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2">
                  <div
                    className="bg-blue-600 dark:bg-blue-500 h-2 rounded-full transition-all duration-300"
                    style={{
                      width: `${
                        job.total_documents > 0
                          ? (job.processed_documents / job.total_documents) *
                            100
                          : 0
                      }%`,
                    }}
                  />
                </div>
              </div>

              {/* Statistics Grid */}
              <div className="grid grid-cols-3 gap-4 pt-2">
                <div className="text-center">
                  <div className="text-2xl font-bold text-gray-900 dark:text-white">
                    {job.total_documents}
                  </div>
                  <div className="text-xs text-gray-500 dark:text-gray-400">
                    Total Docs
                  </div>
                </div>
                <div className="text-center">
                  <div className="text-2xl font-bold text-blue-600 dark:text-blue-400">
                    {job.processed_documents}
                  </div>
                  <div className="text-xs text-gray-500 dark:text-gray-400">
                    Processed
                  </div>
                </div>
                <div className="text-center">
                  <div className="text-2xl font-bold text-orange-600 dark:text-orange-400">
                    {job.queued_documents}
                  </div>
                  <div className="text-xs text-gray-500 dark:text-gray-400">
                    In Queue
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
