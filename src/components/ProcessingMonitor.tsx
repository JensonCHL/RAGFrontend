'use client';

import { useState, useEffect } from 'react';
import { ChevronDown, ChevronUp, Activity, Clock, CheckCircle } from 'lucide-react';

interface ProcessingDocument {
    doc_id: string;
    company_id: string;
    file_name: string;
    progress: number;
    message: string;
    current_page?: number;
    total_pages?: number;
    wait_time_seconds?: number;
}

interface QueueStatus {
    success: boolean;
    active_workers: number;
    max_workers: number;
    available_workers: number;
    queue_full: boolean;
    currently_processing: ProcessingDocument[];
    queued_documents: ProcessingDocument[];
    total_processing: number;
    total_queued: number;
}

export default function ProcessingMonitor() {
    const [isExpanded, setIsExpanded] = useState(false);
    const [queueStatus, setQueueStatus] = useState<QueueStatus | null>(null);
    const [isLoading, setIsLoading] = useState(false);

    const fetchQueueStatus = async () => {
        try {
            setIsLoading(true);
            const response = await fetch('/api/proxy/api/processing-queue-status');
            const data = await response.json();
            setQueueStatus(data);
        } catch (error) {
            console.error('Failed to fetch queue status:', error);
        } finally {
            setIsLoading(false);
        }
    };

    // Fetch on mount and when expanded
    useEffect(() => {
        fetchQueueStatus();

        // Auto-refresh every 2 seconds when expanded
        let interval: NodeJS.Timeout | null = null;
        if (isExpanded) {
            interval = setInterval(fetchQueueStatus, 2000);
        }

        return () => {
            if (interval) clearInterval(interval);
        };
    }, [isExpanded]);

    const formatWaitTime = (seconds: number) => {
        if (seconds < 60) return `${seconds}s`;
        const minutes = Math.floor(seconds / 60);
        const secs = seconds % 60;
        return `${minutes}m ${secs}s`;
    };

    const workerUtilization = queueStatus
        ? ((queueStatus.active_workers / queueStatus.max_workers) * 100).toFixed(0)
        : 0;

    return (
        <div className="bg-white rounded-lg shadow-md border border-gray-200 mb-6">
            {/* Header - Always Visible */}
            <button
                onClick={() => setIsExpanded(!isExpanded)}
                className="w-full px-6 py-4 flex items-center justify-between hover:bg-gray-50 transition-colors"
            >
                <div className="flex items-center gap-4">
                    <Activity className="w-5 h-5 text-blue-600" />
                    <div className="text-left">
                        <h3 className="font-semibold text-gray-900">Processing Monitor</h3>
                        <p className="text-sm text-gray-600">
                            {queueStatus ? (
                                <>
                                    <span className="font-medium text-blue-600">
                                        {queueStatus.active_workers}/{queueStatus.max_workers}
                                    </span>
                                    {' '}workers active
                                    {queueStatus.total_queued > 0 && (
                                        <span className="ml-2 text-orange-600">
                                            • {queueStatus.total_queued} queued
                                        </span>
                                    )}
                                </>
                            ) : (
                                'Loading...'
                            )}
                        </p>
                    </div>
                </div>

                <div className="flex items-center gap-3">
                    {/* Worker Utilization Badge */}
                    {queueStatus && (
                        <div className="flex items-center gap-2">
                            <div className="w-24 h-2 bg-gray-200 rounded-full overflow-hidden">
                                <div
                                    className={`h-full transition-all ${Number(workerUtilization) >= 90
                                            ? 'bg-red-500'
                                            : Number(workerUtilization) >= 70
                                                ? 'bg-orange-500'
                                                : 'bg-green-500'
                                        }`}
                                    style={{ width: `${workerUtilization}%` }}
                                />
                            </div>
                            <span className="text-sm font-medium text-gray-600">
                                {workerUtilization}%
                            </span>
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
            {isExpanded && queueStatus && (
                <div className="px-6 pb-6 space-y-4 border-t border-gray-200 pt-4">
                    {/* Stats Grid */}
                    <div className="grid grid-cols-4 gap-4">
                        <div className="bg-blue-50 rounded-lg p-3">
                            <div className="text-xs text-blue-600 font-medium mb-1">Active Workers</div>
                            <div className="text-2xl font-bold text-blue-700">
                                {queueStatus.active_workers}
                            </div>
                        </div>
                        <div className="bg-green-50 rounded-lg p-3">
                            <div className="text-xs text-green-600 font-medium mb-1">Available</div>
                            <div className="text-2xl font-bold text-green-700">
                                {queueStatus.available_workers}
                            </div>
                        </div>
                        <div className="bg-purple-50 rounded-lg p-3">
                            <div className="text-xs text-purple-600 font-medium mb-1">Processing</div>
                            <div className="text-2xl font-bold text-purple-700">
                                {queueStatus.total_processing}
                            </div>
                        </div>
                        <div className="bg-orange-50 rounded-lg p-3">
                            <div className="text-xs text-orange-600 font-medium mb-1">Queued</div>
                            <div className="text-2xl font-bold text-orange-700">
                                {queueStatus.total_queued}
                            </div>
                        </div>
                    </div>

                    {/* Currently Processing */}
                    {queueStatus.currently_processing.length > 0 && (
                        <div>
                            <h4 className="font-semibold text-gray-900 mb-2 flex items-center gap-2">
                                <Activity className="w-4 h-4 text-blue-600" />
                                Currently Processing ({queueStatus.currently_processing.length})
                            </h4>
                            <div className="space-y-2 max-h-60 overflow-y-auto">
                                {queueStatus.currently_processing.map((doc) => (
                                    <div
                                        key={doc.doc_id}
                                        className="bg-blue-50 rounded-lg p-3 border border-blue-200"
                                    >
                                        <div className="flex items-start justify-between">
                                            <div className="flex-1">
                                                <div className="font-medium text-gray-900 text-sm">
                                                    {doc.file_name}
                                                </div>
                                                <div className="text-xs text-gray-600 mt-1">
                                                    Company: {doc.company_id}
                                                </div>
                                                <div className="text-xs text-blue-600 mt-1">
                                                    {doc.message}
                                                </div>
                                            </div>
                                            <div className="text-right ml-4">
                                                <div className="text-sm font-semibold text-blue-700">
                                                    {doc.progress}%
                                                </div>
                                                {doc.current_page && doc.total_pages && (
                                                    <div className="text-xs text-gray-600 mt-1">
                                                        Page {doc.current_page}/{doc.total_pages}
                                                    </div>
                                                )}
                                            </div>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </div>
                    )}

                    {/* Queued Documents */}
                    {queueStatus.queued_documents.length > 0 && (
                        <div>
                            <h4 className="font-semibold text-gray-900 mb-2 flex items-center gap-2">
                                <Clock className="w-4 h-4 text-orange-600" />
                                Waiting in Queue ({queueStatus.queued_documents.length})
                            </h4>
                            <div className="space-y-2 max-h-60 overflow-y-auto">
                                {queueStatus.queued_documents.map((doc) => (
                                    <div
                                        key={doc.doc_id}
                                        className="bg-orange-50 rounded-lg p-3 border border-orange-200"
                                    >
                                        <div className="flex items-start justify-between">
                                            <div className="flex-1">
                                                <div className="font-medium text-gray-900 text-sm">
                                                    {doc.file_name}
                                                </div>
                                                <div className="text-xs text-gray-600 mt-1">
                                                    Company: {doc.company_id}
                                                </div>
                                                <div className="text-xs text-orange-600 mt-1">
                                                    {doc.message}
                                                </div>
                                            </div>
                                            <div className="text-right ml-4">
                                                <div className="text-xs text-gray-600">
                                                    Waiting: {formatWaitTime(doc.wait_time_seconds || 0)}
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </div>
                    )}

                    {/* Empty State */}
                    {queueStatus.currently_processing.length === 0 && queueStatus.queued_documents.length === 0 && (
                        <div className="text-center py-8 text-gray-500">
                            <CheckCircle className="w-12 h-12 mx-auto mb-2 text-green-500" />
                            <p className="font-medium">No active processing</p>
                            <p className="text-sm">All workers are idle</p>
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}
