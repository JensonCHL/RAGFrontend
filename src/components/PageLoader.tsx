"use client";

import React from "react";

interface PageLoaderProps {
  size?: "small" | "medium" | "large";
  text?: string;
  fullScreen?: boolean;
}

/**
 * Page loading component with brand colors (blue-to-red gradient)
 * Matches the existing loading-border style
 */
const PageLoader: React.FC<PageLoaderProps> = ({
  size = "medium",
  text,
  fullScreen = false,
}) => {
  // Size configurations
  const sizeConfig = {
    small: {
      container: "w-8 h-8",
      bar: "h-1",
      text: "text-xs",
    },
    medium: {
      container: "w-12 h-12",
      bar: "h-1.5",
      text: "text-sm",
    },
    large: {
      container: "w-16 h-16",
      bar: "h-2",
      text: "text-base",
    },
  };

  const config = sizeConfig[size];

  const wrapperClass = fullScreen
    ? "fixed inset-0 z-50 flex items-center justify-center bg-gray-50/80 dark:bg-gray-900/80 backdrop-blur-sm"
    : "flex items-center justify-center p-4";

  return (
    <div className={wrapperClass}>
      <div className="flex flex-col items-center gap-4">
        {/* Animated gradient bar */}
        <div className="w-48 overflow-hidden rounded-full bg-gray-200 dark:bg-gray-700">
          <div
            className={`${config.bar} rounded-full animate-loading-bar`}
            style={{
              background:
                "linear-gradient(90deg, #3b82f6, #8b5cf6, #ef4444, #8b5cf6, #3b82f6)",
              backgroundSize: "200% 100%",
            }}
          />
        </div>

        {/* Optional loading text */}
        {text && (
          <p
            className={`${config.text} text-gray-600 dark:text-gray-400 animate-pulse`}
          >
            {text}
          </p>
        )}
      </div>
    </div>
  );
};

export default PageLoader;
