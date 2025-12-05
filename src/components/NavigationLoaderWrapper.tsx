"use client";

import { Suspense } from "react";
import NavigationLoader from "./NavigationLoader";

/**
 * Wrapper for NavigationLoader with Suspense boundary
 * Required because NavigationLoader uses useSearchParams
 */
export default function NavigationLoaderWrapper() {
  return (
    <Suspense fallback={null}>
      <NavigationLoader />
    </Suspense>
  );
}
