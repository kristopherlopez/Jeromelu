import { notFound } from "next/navigation";
import AdminClient from "./AdminClient";

export default function AdminPage() {
  if (process.env.NODE_ENV !== "development") {
    notFound();
  }

  return (
    <main className="min-h-screen px-6 py-8 sm:px-8">
      <div className="mx-auto max-w-6xl">
        <h1
          className="mb-6 text-xl font-bold tracking-tight"
          style={{ color: "var(--tigers-orange)" }}
        >
          Pipeline Admin
        </h1>
        <AdminClient />
      </div>
    </main>
  );
}
