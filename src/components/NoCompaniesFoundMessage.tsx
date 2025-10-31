import React from 'react';

interface NoCompaniesFoundMessageProps {
  searchTerm: string;
}

const NoCompaniesFoundMessage: React.FC<NoCompaniesFoundMessageProps> = ({ searchTerm }) => {
  return (
    <div className="bg-white rounded-lg shadow p-8 text-center">
      <svg className="mx-auto h-12 w-12 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
      </svg>
      <h3 className="mt-4 text-lg font-medium text-gray-900">
        {searchTerm ? 'No matching companies found' : 'No companies found'}
      </h3>
      <p className="mt-2 text-gray-500">
        {searchTerm 
          ? `No companies or contracts match your search for "${searchTerm}".` 
          : 'Upload a folder or create a company to get started.'}
      </p>
    </div>
  );
};

export default NoCompaniesFoundMessage;
