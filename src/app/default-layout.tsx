import Sidebar from "@/components/Sidebar";

export default function DefaultLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="flex h-screen bg-gray-50 dark:bg-gray-900 overflow-hidden">
      <Sidebar />
      <div className="flex-1 overflow-auto bg-gray-50 dark:bg-gray-900">
        {children}
      </div>
    </div>
  );
}
