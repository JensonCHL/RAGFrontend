'use client'
import { useState, useEffect } from 'react';

// Define the type for our data rows
interface ExtractedData {
  id: number;
  company_name: string;
  file_name: string;
  index_name: string;
  result: {
    value: string | number | null;
    page: number | null;
  };
  created_at: string;
}

// Type for grouped data
type GroupedData = {
  [indexName: string]: ExtractedData[];
};

// Type for managing open/closed state of accordions
type AccordionState = {
  [indexName: string]: boolean;
};

export default function IndexingPage() {
  const [indexName, setIndexName] = useState('');
  const [apiKey, setApiKey] = useState(''); // State for API Key
  const [isIndexing, setIsIndexing] = useState(false);
  const [statusMessages, setStatusMessages] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [tableData, setTableData] = useState<ExtractedData[]>([]);
  const [groupedData, setGroupedData] = useState<GroupedData>({});
  const [openAccordions, setOpenAccordions] = useState<AccordionState>({});

  // Function to fetch data from the database
  const fetchData = async () => {
    try {
      const response = await fetch('http://localhost:5000/api/get-all-data');
      const result = await response.json();
      if (result.success) {
        setTableData(result.data);
        // Group data after fetching
        const grouped = result.data.reduce((acc: GroupedData, item: ExtractedData) => {
          const key = item.index_name;
          if (!acc[key]) {
            acc[key] = [];
          }
          acc[key].push(item);
          return acc;
        }, {});
        setGroupedData(grouped);
      } else {
        console.error('Failed to fetch data:', result.error);
        setError(`Failed to fetch data: ${result.error}`)
      }
    } catch (err) {
      console.error('Error fetching data:', err);
      setError('Error fetching data. Is the backend server running?')
    }
  };

  // Effect to listen for Server-Sent Events (SSE)
  useEffect(() => {
    // Fetch initial data on mount
    fetchData();

    const eventSource = new EventSource('http://localhost:5000/events/processing-updates');

    eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === 'indexing_status') {
          setStatusMessages(prev => [...prev, data.message]);
          if (data.message.includes('Job complete') || data.message.includes('Job failed')) {
            setIsIndexing(false);
            // Refresh data after job is complete
            fetchData();
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

    return () => {
      eventSource.close();
    };
  }, []);

  const handleStartIndexing = async () => {
    if (!indexName.trim()) {
      setError('Index name cannot be empty.');
      return;
    }
    if (!apiKey.trim()) {
      setError('API Key cannot be empty to start an indexing job.');
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
          'Authorization': `Bearer ${apiKey}`,
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

  const handleDeleteIndex = async (indexToDelete: string) => {
    if (!window.confirm(`Are you sure you want to delete all data for the index "${indexToDelete}"? This action cannot be undone.`)) {
      return;
    }

    setError(null);

    try {
      const response = await fetch(`http://localhost:5000/api/index/${indexToDelete}` , {
        method: 'DELETE',
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.error || 'Failed to delete index.');
      }

      alert(data.message); // Show success message
      fetchData(); // Refresh the data

    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'An unknown error occurred.';
      setError(errorMessage);
    }
  };

  const toggleAccordion = (key: string) => {
    setOpenAccordions(prev => ({ ...prev, [key]: !prev[key] }));
  };

  return (
    <div className="min-h-screen bg-gray-50 p-8">
      <div className="max-w-7xl mx-auto bg-white rounded-lg shadow-md p-8">
        <header className="border-b border-gray-200 pb-4 mb-6">
          <h1 className="text-2xl font-bold text-gray-900">Manage Indexes</h1>
          <p className="text-sm text-gray-600 mt-1">
            Create a new index or delete an existing one.
          </p>
        </header>

        <div className="space-y-6">

          {/* Create Index Section */}
          <div>
            <label htmlFor="indexName" className="block text-sm font-medium text-gray-700">
              Create New Index
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

      {/* Data Table for Debugging */}
      <div className="max-w-7xl mx-auto bg-white rounded-lg shadow-md p-8 mt-8">
        <h2 className="text-xl font-bold text-gray-900 mb-4">Database Content</h2>
        <div className="space-y-4">
          {Object.keys(groupedData).length > 0 ? (
            Object.keys(groupedData).map((indexKey) => (
              <div key={indexKey} className="border border-gray-200 rounded-lg">
                <div className="w-full flex justify-between items-center p-4 bg-gray-50">
                  <button
                    onClick={() => toggleAccordion(indexKey)}
                    className="flex-1 flex items-center text-left focus:outline-none"
                  >
                    <h3 className="text-lg font-medium text-gray-800">{indexKey}</h3>
                    <span className={`ml-4 transform transition-transform ${openAccordions[indexKey] ? 'rotate-180' : ''}`}>
                      <svg className="w-5 h-5 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 9l-7 7-7-7"></path></svg>
                    </span>
                  </button>
                  <button 
                    onClick={() => handleDeleteIndex(indexKey)}
                    className="ml-4 px-3 py-1 border border-transparent text-sm font-medium rounded-md text-white bg-red-600 hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-red-500"
                  >
                    Delete
                  </button>
                </div>
                {openAccordions[indexKey] && (
                  <div className="overflow-x-auto p-4">
                    <table className="min-w-full divide-y divide-gray-200">
                      <thead className="bg-gray-50">
                        <tr>
                          <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Company</th>
                          <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">File Name</th>
                          <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Value</th>
                          <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Page</th>
                        </tr>
                      </thead>
                      <tbody className="bg-white divide-y divide-gray-200">
                        {groupedData[indexKey].map((row) => (
                          <tr key={row.id}>
                            <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{row.company_name}</td>
                            <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{row.file_name}</td>
                            <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-800 font-medium">{String(row.result?.value ?? 'N/A')}</td>
                            <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{row.result?.page ?? 'N/A'}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            ))
          ) : (
            <p className="text-center text-gray-500">No data in database yet.</p>
          )}
        </div>
      </div>
    </div>
  );
}