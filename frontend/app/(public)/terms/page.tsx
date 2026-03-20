import { Metadata } from "next";

export const metadata: Metadata = {
  title: "Términos de Servicio | Luka",
  description: "Reglas y condiciones de uso para la plataforma Luka.",
};

export default function TermsPage() {
  return (
    <article className="max-w-none text-slate-600 leading-relaxed px-2">
      <h1 className="text-3xl font-bold tracking-tight text-slate-900 mb-6">Términos de Servicio</h1>
      <p className="mb-8 italic text-slate-500">Última actualización: 20 de marzo de 2026</p>

      <section className="mb-10 text-pretty">
        <h2 className="text-xl font-bold text-slate-800 mb-4 border-b border-slate-100 pb-2">1. Aceptación de los Términos</h2>
        <p className="mb-4">
          Al acceder y utilizar **Luka**, usted acepta estar sujeto a estos Términos de Servicio. 
          Si no está de acuerdo con alguna parte de estos términos, no debe utilizar nuestra plataforma.
        </p>
      </section>

      <section className="mb-10 text-pretty">
        <h2 className="text-xl font-bold text-slate-800 mb-4 border-b border-slate-100 pb-2">2. Descripción del Servicio</h2>
        <p className="mb-4">
          Luka es una herramienta de gestión de finanzas personales que permite a los usuarios centralizar la 
          información de sus cuentas bancarias chilenas y gestionar sus gastos mediante una interfaz web y de WhatsApp.
        </p>
      </section>

      <section className="mb-10 text-pretty">
        <h2 className="text-xl font-bold text-slate-800 mb-4 border-b border-slate-100 pb-2">3. Responsabilidad del Usuario</h2>
        <ul className="list-disc pl-5 mt-2 space-y-3">
          <li>Usted es responsable de mantener la confidencialidad de su cuenta y contraseña.</li>
          <li>Usted garantiza que tiene el derecho legal de conectar las cuentas bancarias que vincule mediante Fintoc.</li>
          <li>Usted se compromete a no utilizar el servicio para fines ilícitos o fraudulentos.</li>
        </ul>
      </section>

      <section className="mb-10 text-pretty">
        <h2 className="text-xl font-bold text-slate-800 mb-4 border-b border-slate-100 pb-2">4. Limitación de Responsabilidad</h2>
        <p className="mb-4">
          Luka es una herramienta de apoyo informativo. <strong className="text-slate-900">No constituye asesoría financiera, legal o contable profesional.</strong> 
          No somos responsables por decisiones financieras tomadas basadas en los datos presentados por la aplicación, 
          ni por errores derivados de información entregada por terceros (como bancos o APIs externas).
        </p>
      </section>

      <section className="mb-10 text-pretty">
        <h2 className="text-xl font-bold text-slate-800 mb-4 border-b border-slate-100 pb-2">5. Propiedad Intelectual</h2>
        <p className="mb-4">
          Todo el contenido, diseño y código de Luka es propiedad exclusiva de Rafael Labra y está protegido por las leyes de propiedad intelectual de Chile.
        </p>
      </section>

      <section className="text-pretty">
        <h2 className="text-xl font-bold text-slate-800 mb-4 border-b border-slate-100 pb-2">6. Ley Aplicable y Jurisdicción</h2>
        <p className="mb-4">
          Estos términos se rigen por las leyes de la República de Chile. Cualquier controversia será sometida a la jurisdicción de los tribunales ordinarios de Santiago.
        </p>
      </section>
    </article>
  );
}
