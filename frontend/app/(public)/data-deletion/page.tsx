import { Metadata } from "next";

export const metadata: Metadata = {
  title: "Eliminación de Datos | Luka",
  description: "Instrucciones sobre cómo solicitar la eliminación de sus datos personales de Luka.",
};

export default function DataDeletionPage() {
  return (
    <article className="max-w-none text-slate-600 leading-relaxed px-2">
      <h1 className="text-3xl font-bold tracking-tight text-slate-900 mb-6">Instrucciones de Eliminación de Datos</h1>
      <p className="mb-8 italic text-slate-500">Última actualización: 20 de marzo de 2026</p>

      <p className="mb-10 font-medium text-slate-800 text-pretty">
        En cumplimiento con las políticas de Meta y la ley chilena, proporcionamos un método claro y directo para que los usuarios eliminen su información de nuestra plataforma.
      </p>

      <section className="mb-10 text-pretty">
        <h2 className="text-xl font-bold text-slate-800 mb-4 border-b border-slate-100 pb-2">¿Cómo eliminar mis datos?</h2>
        <p className="mb-4">Existen dos formas de solicitar la eliminación completa de su cuenta y datos asociados:</p>
        <div className="mt-6 space-y-6">
          <div className="bg-slate-50 p-6 rounded-xl border border-slate-200">
            <h3 className="font-semibold text-slate-900 mb-2">Opción 1: Vía Correo Electrónico</h3>
            <p className="text-slate-600">
              Envíe un correo electrónico desde la cuenta registrada en Luka a: <br />
              <span className="font-mono text-indigo-600 font-bold">rafaellabra96@gmail.com</span><br />
              Con el asunto: <strong>"Solicitud de eliminación de datos - Luka"</strong>.
            </p>
          </div>
          
          <div className="bg-slate-50 p-6 rounded-xl border border-slate-200">
            <h3 className="font-semibold text-slate-900 mb-2">Opción 2: Dentro de la Aplicación</h3>
            <p className="text-slate-600">
              1. Inicie sesión en su cuenta de Luka.<br />
              2. Diríjase a la sección de **Configuración**.<br />
              3. Haga clic en el botón **"Eliminar Cuenta"** al final de la página.<br />
              4. Confirme su decisión.
            </p>
          </div>
        </div>
      </section>

      <section className="mb-10 text-pretty">
        <h2 className="text-xl font-bold text-slate-800 mb-4 border-b border-slate-100 pb-2">¿Qué datos se eliminan?</h2>
        <p className="mb-4">Al procesar su solicitud, eliminaremos de forma permanente:</p>
        <ul className="list-disc pl-5 mt-2 space-y-3 text-slate-600">
          <li>Perfil de usuario (nombre, correo).</li>
          <li>Tokens de conexión con Fintoc y Meta.</li>
          <li>Historial de transacciones y categorizaciones.</li>
          <li>Sesiones activas en WhatsApp.</li>
        </ul>
      </section>

      <section className="text-pretty">
        <h2 className="text-xl font-bold text-slate-800 mb-4 border-b border-slate-100 pb-2">Plazos de Procesamiento</h2>
        <p className="mb-4">
          Las solicitudes enviadas por correo electrónico se procesarán en un plazo máximo de <strong className="text-slate-900">48 horas hábiles</strong>. Una vez completada la eliminación, recibirá un correo de confirmación.
        </p>
      </section>
    </article>
  );
}
