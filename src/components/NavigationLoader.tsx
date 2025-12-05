"use client";

import { useEffect, useState } from "react";
import { usePathname, useSearchParams } from "next/navigation";

/**
 * Navigation progress bar that shows during page transitions
 * Uses brand colors (blue → purple → red gradient)
 */
export default function NavigationLoader() {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const [isNavigating, setIsNavigating] = useState(false);
  const [progress, setProgress] = useState(0);

  useEffect(() => {
    // Reset progress when navigation completes
    setIsNavigating(false);
    setProgress(100);

    const timeout = setTimeout(() => {
      setProgress(0);
    }, 300);

    return () => clearTimeout(timeout);
  }, [pathname, searchParams]);

  // Listen for link clicks to start loading
  useEffect(() => {
    const handleClick = (e: MouseEvent) => {
      const target = e.target as HTMLElement;
      const anchor = target.closest("a");

      if (anchor) {
        const href = anchor.getAttribute("href");
        // Only show loader for internal navigation
        if (href && href.startsWith("/") && href !== pathname) {
          setIsNavigating(true);
          setProgress(0);

          // Animate progress
          let currentProgress = 0;
          const interval = setInterval(() => {
            currentProgress += Math.random() * 15;
            if (currentProgress >= 90) {
              clearInterval(interval);
              currentProgress = 90;
            }
            setProgress(currentProgress);
          }, 100);
        }
      }
    };

    document.addEventListener("click", handleClick);
    return () => document.removeEventListener("click", handleClick);
  }, [pathname]);

  if (!isNavigating && progress === 0) {
    return null;
  }

  return (
    <div className="fixed top-0 left-0 right-0 z-[9999] h-1">
      <div
        className="h-full transition-all duration-300 ease-out"
        style={{
          width: `${progress}%`,
          background: "linear-gradient(90deg, #3b82f6, #8b5cf6, #ef4444)",
          boxShadow: "0 0 10px rgba(59, 130, 246, 0.5)",
        }}
      />
    </div>
  );
}
