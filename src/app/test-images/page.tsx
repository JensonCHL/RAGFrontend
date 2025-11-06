'use client';

import Image from 'next/image';

export default function TestImagesPage() {
  return (
    <div className="min-h-screen bg-gray-50 flex flex-col items-center justify-center py-12">
      <h1 className="text-3xl font-bold mb-8">Image Test Page</h1>
      
      <div className="flex space-x-8">
        <div className="flex flex-col items-center">
          <div className="h-24 w-24 relative bg-white p-2 rounded-lg shadow">
            <Image 
              src="/lintasarta-logo.png" 
              alt="Lintasarta Logo" 
              fill
              className="object-contain"
            />
          </div>
          <span className="text-sm text-gray-600 mt-2">Lintasarta</span>
        </div>
        
        <div className="flex flex-col items-center">
          <div className="h-24 w-24 relative bg-white p-2 rounded-lg shadow">
            <Image 
              src="/cloudeka-logo.png" 
              alt="Cloudeka Logo" 
              fill
              className="object-contain"
            />
          </div>
          <span className="text-sm text-gray-600 mt-2">Cloudeka</span>
        </div>
        
        <div className="flex flex-col items-center">
          <div className="h-24 w-24 relative bg-white p-2 rounded-lg shadow">
            <Image 
              src="/dekacode-logo.png" 
              alt="DekaCode Logo" 
              fill
              className="object-contain"
            />
          </div>
          <span className="text-sm text-gray-600 mt-2">DekaCode</span>
        </div>
      </div>
      
      <div className="mt-8 text-center">
        <p className="text-gray-600">If you can see the images above, they are working correctly.</p>
        <p className="text-gray-600">If not, there may be an issue with the image files or Next.js configuration.</p>
      </div>
    </div>
  );
}