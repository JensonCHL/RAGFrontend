
'use client';

import { useState, useEffect } from 'react';

export default function IndexingPage() {
  const [indexName, setIndexName] = useState('');
  const [isIndexing, setIsIndexing] = useState(false);
  const [statusMessages, setStatusMessages] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);

  // Effect to listen for Server-Sent Events (SSE)
  useEffect(() => {
    const eventSource = new EventSource('http://localhost:5000/events/processing-updates');

    eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        // We only care about indexing status messages on this page
        if (data.type === 'indexing_status') {
          setStatusMessages(prev => [...prev, data.message]);
          if (data.message.startsWith('Job complete') || data.message.startsWith('Job failed')) {
            setIsIndexing(false);
          }
        }
      } catch (error) {
        console.error('Failed to parse SSE message:', error);
      }
    };

    eventSource.onerror = (err) => {
      console.error('SSE error:', err);
      setError('Connection to status updates failed. Please try refreshing the page.');
      eventSource.close();
    };

    // Cleanup on component unmount
    return () => {
      eventSource.close();
    };
  }, []);

  const handleStartIndexing = async () => {
    if (!indexName.trim()) {
      setError('Index name cannot be empty.');
      return;
    }

    setIsIndexing(true);
    setStatusMessages([]);
    setError(null);

    try {
      const response = await fetch('http://localhost:5000/api/create-index', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ index_name: indexName }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.error || 'Failed to start indexing job.');
      }

      setStatusMessages([data.message]);

    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'An unknown error occurred.';
      setError(errorMessage);
      setIsIndexing(false);
    }
  };

  return (
    <div className="min-h-screen bg-gray-50 p-8">
      <div className="max-w-3xl mx-auto bg-white rounded-lg shadow-md p-8">
        <header className="border-b border-gray-200 pb-4 mb-6">
          <h1 className="text-2xl font-bold text-gray-900">Create New Index</h1>
          <p className="text-sm text-gray-600 mt-1">
            Run a job to extract a new piece of information from all documents.
          </p>
        </header>

        <div className="space-y-6">
          <div>
            <label htmlFor="indexName" className="block text-sm font-medium text-gray-700">
              Index Name
            </label>
            <div className="mt-1 flex rounded-md shadow-sm">
              <input
                type="text"
                id="indexName"
                value={indexName}
                onChange={(e) => setIndexName(e.target.value)}
                className="flex-1 block w-full rounded-none rounded-l-md border-gray-300 focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
                placeholder='e.g., "End Date", "Contract Value"'
                disabled={isIndexing}
              />
              <button
                onClick={handleStartIndexing}
                disabled={isIndexing}
                className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-r-md text-white bg-blue-600 hover:bg-blue-700 disabled:bg-gray-400 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
              >
                {isIndexing ? 'Indexing...' : 'Start Indexing'}
              </button>
            </div>
            {error && <p className="mt-2 text-sm text-red-600">{error}</p>}
          </div>

          {statusMessages.length > 0 && (
            <div className="bg-gray-50 rounded-lg p-4">
              <h2 className="text-lg font-medium text-gray-800 mb-2">Indexing Status</h2>
              <div className="space-y-2 text-sm text-gray-700 font-mono">
                {statusMessages.map((msg, index) => (
                  <p key={`${index}-${msg}`}>{`[${new Date().toLocaleTimeString()}] ${msg}`}</p>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
