import { redirect } from 'next/navigation';
import { isAuthenticated } from '@/utils/auth';

export default async function ProtectedPage() {
  const authenticated = await isAuthenticated();
  
  if (!authenticated) {
    redirect('/login');
  }

  return (
    <div className="min-h-screen bg-gray-50 p-8">
      <div className="max-w-4xl mx-auto">
        <h1 className="text-3xl font-bold text-gray-900 mb-8">Protected Page</h1>
        <div className="bg-white rounded-lg shadow p-6">
          <p className="text-gray-700">
            This page is protected and can only be accessed by authenticated users.
          </p>
        </div>
      </div>
    </div>
  );
}