import React from 'react';

interface LoadingSpinnerProps {
  size?: 'small' | 'medium' | 'large';
  color?: string;
  className?: string;
}

const LoadingSpinner: React.FC<LoadingSpinnerProps> = ({
  size = 'medium',
  color = 'currentColor',
  className = '',
}) => {
  let spinnerSize;
  switch (size) {
    case 'small':
      spinnerSize = 'h-4 w-4';
      break;
    case 'large':
      spinnerSize = 'h-12 w-12';
      break;
    case 'medium':
    default:
      spinnerSize = 'h-8 w-8';
      break;
  }

  return (
    <div
      className={`animate-spin rounded-full border-2 border-t-2 border-${color} ${spinnerSize} ${className}`}
      style={{ borderTopColor: color, borderColor: `${color} transparent ${color} transparent` }}
      role="status"
    >
      <span className="sr-only">Loading...</span>
    </div>
  );
};

export default LoadingSpinner;
