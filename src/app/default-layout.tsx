import FloatingNavbar from "@/components/FloatingNavbar";

export default function DefaultLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <>
      <FloatingNavbar />
      <div className="pt-16">
        {children}
      </div>
    </>
  );
}