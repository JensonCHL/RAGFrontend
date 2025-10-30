import React from 'react';

interface ProcessingProgressBarProps {
  label: string;
  current: number;
  total: number;
  colorClass: string;
  progress: number;
}

const ProcessingProgressBar: React.FC<ProcessingProgressBarProps> = ({
  label,
  current,
  total,
  colorClass,
  progress,
}) => {
  return (
    <div className="mt-3">
      <div className="flex justify-between text-xs text-gray-600 mb-1">
        <span>{label}</span>
        <span>{current}/{total}</span>
      </div>
      <div className="w-full bg-gray-200 rounded-full h-1.5">
        <div 
          className={`${colorClass} h-1.5 rounded-full transition-all duration-300 ease-out`}
          style={{ width: `${progress}%` }}
        ></div>
      </div>
    </div>
  );
};

export default ProcessingProgressBar;