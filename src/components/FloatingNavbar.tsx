'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useState, useEffect } from 'react';
import { useSession, signOut } from 'next-auth/react';
import { useRouter } from 'next/navigation';

export default function FloatingNavbar() {
  const router = useRouter();
  const pathname = usePathname();
  const [isScrolled, setIsScrolled] = useState(false);
  const { data: session, status } = useSession();

  // Check if this is a new browser session
  useEffect(() => {
    // Check if there's a session indicator in localStorage
    const sessionStarted = localStorage.getItem('sessionStarted');

    // If there's no session indicator, this might be a new browser session
    if (!sessionStarted && status === 'authenticated') {
      // Set session indicator
      localStorage.setItem('sessionStarted', Date.now().toString());
    }

    // If we have a session but no indicator, it might mean browser was closed and reopened
    if (status === 'authenticated' && !sessionStarted) {
      // Force a session check
      router.push('/login?sessionExpired=true');
    }
  }, [status, router]);

  // Clean up session indicator on logout
  useEffect(() => {
    if (status === 'unauthenticated') {
      localStorage.removeItem('sessionStarted');
    }
  }, [status]);

  useEffect(() => {
    const handleScroll = () => {
      setIsScrolled(window.scrollY > 10);
    };

    window.addEventListener('scroll', handleScroll);
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  const handleLogout = async () => {
    localStorage.removeItem('sessionStarted');
    await signOut({ callbackUrl: '/login' });
  };

  return (
    <nav className={`fixed top-0 left-0 right-0 z-50 transition-all duration-300 ${
      isScrolled
        ? 'bg-white shadow-lg backdrop-blur-sm bg-opacity-90'
        : 'bg-white shadow'
    }`}>
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between h-16">
          <div className="flex">
            <div className="flex-shrink-0 flex items-center">
              <h1 className="text-xl font-bold text-gray-900">Document Ingestion</h1>
            </div>
            <div className="hidden sm:ml-6 sm:flex sm:space-x-8">
              <Link
                href="/dashboard"
                className={`${pathname === '/dashboard' ? 'border-blue-500 text-gray-900' : 'border-transparent text-gray-500 hover:border-gray-300 hover:text-gray-700'} inline-flex items-center px-1 pt-1 border-b-2 text-sm font-medium transition-colors duration-300 ease-in-out delay-75`}
              >
                Dashboard
              </Link>
              <Link
                href="/file-management"
                className={`${pathname === '/file-management' ? 'border-blue-500 text-gray-900' : 'border-transparent text-gray-500 hover:border-gray-300 hover:text-gray-700'} inline-flex items-center px-1 pt-1 border-b-2 text-sm font-medium transition-colors duration-300 ease-in-out delay-75`}
              >
                File Management
              </Link>
              <Link
                href="/indexing"
                className={`${pathname === '/indexing' ? 'border-blue-500 text-gray-900' : 'border-transparent text-gray-500 hover:border-gray-300 hover:text-gray-700'} inline-flex items-center px-1 pt-1 border-b-2 text-sm font-medium transition-colors duration-300 ease-in-out delay-75`}
              >
                Indexing
              </Link>
            </div>
          </div>

          {status === 'authenticated' && (
            <div className="flex items-center">
              <span className="text-sm text-gray-700 mr-4 hidden md:inline">
                Welcome, {(session.user as any)?.username || session.user?.name}
              </span>
              <button
                onClick={handleLogout}
                className="text-sm text-gray-700 hover:text-gray-900 font-medium"
              >
                Logout
              </button>
            </div>
          )}
        </div>
      </div>
    </nav>
  );
}