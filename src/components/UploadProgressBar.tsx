import React from "react";

interface UploadProgressBarProps {
  isUploading: boolean;
  progress: number | null;
}

const UploadProgressBar: React.FC<UploadProgressBarProps> = ({
  isUploading,
  progress,
}) => {
  if (!isUploading || progress === null) {
    return null;
  }

  return (
    <div className="mb-6">
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-4 transition-colors duration-300">
        <div className="flex justify-between mb-1">
          <span className="text-sm font-medium text-gray-700 dark:text-gray-300">
            Uploading files...
          </span>
          <span className="text-sm font-medium text-gray-700 dark:text-gray-300">
            {progress}%
          </span>
        </div>
        <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2.5">
          <div
            className="bg-blue-600 h-2.5 rounded-full transition-all duration-300 ease-out"
            style={{ width: `${progress}%` }}
          ></div>
        </div>
      </div>
    </div>
  );
};

export default UploadProgressBar;
