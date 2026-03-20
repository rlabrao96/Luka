import { ReactNode } from "react";

export default function PublicLayout({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen bg-slate-50 font-sans text-slate-900 selection:bg-indigo-100 selection:text-indigo-900">
      <div className="mx-auto max-w-3xl px-6 py-16 sm:py-24 lg:px-8">
        <div className="mb-12 flex justify-center">
          <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-indigo-600 shadow-lg shadow-indigo-200">
            <span className="text-xl font-bold text-white">L</span>
          </div>
        </div>
        <main className="bg-white p-8 sm:p-12 rounded-2xl shadow-sm border border-slate-200">
          {children}
        </main>
        <footer className="mt-12 text-center text-sm text-slate-500">
          &copy; {new Date().getFullYear()} Luka Finance. Todos los derechos reservados.
        </footer>
      </div>
    </div>
  );
}
