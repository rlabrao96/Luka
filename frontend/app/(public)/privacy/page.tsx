import { Metadata } from "next";

export const metadata: Metadata = {
  title: "Política de Privacidad | Luka",
  description: "Información sobre cómo protegemos sus datos personales en cumplimiento con la Ley 19.628 de Chile.",
};

export default function PrivacyPage() {
  return (
    <article className="max-w-none text-slate-600 leading-relaxed px-2">
      <h1 className="text-3xl font-bold tracking-tight text-slate-900 mb-6">Política de Privacidad</h1>
      <p className="mb-8 italic text-slate-500">Última actualización: 20 de marzo de 2026</p>

      <section className="mb-10 text-pretty">
        <h2 className="text-xl font-bold text-slate-800 mb-4 border-b border-slate-100 pb-2">1. Introducción</h2>
        <p className="mb-4">
          En **Luka**, valoramos su privacidad y estamos comprometidos con la protección de sus datos personales. 
          Esta política explica cómo recopilamos, usamos y protegemos su información en cumplimiento con la 
          **Ley N° 19.628 sobre Protección de la Vida Privada** de la República de Chile.
        </p>
      </section>

      <section className="mb-10 text-pretty">
        <h2 className="text-xl font-bold text-slate-800 mb-4 border-b border-slate-100 pb-2">2. Recopilación de Datos</h2>
        <p className="mb-4">Recopilamos la siguiente información para proporcionar nuestros servicios:</p>
        <ul className="list-disc pl-5 mt-2 space-y-3">
          <li><strong className="text-slate-900">Información de Registro:</strong> Nombre y correo electrónico proporcionados vía Google Auth o registro directo.</li>
          <li><strong className="text-slate-900">Datos Financieros:</strong> Información de transacciones y saldos bancarios obtenida mediante su consentimiento previo a través de <strong className="text-indigo-600">Fintoc</strong>.</li>
          <li><strong className="text-slate-900">Comunicaciones:</strong> Interacciones realizadas a través de nuestra integración oficial con <strong className="text-indigo-600">WhatsApp Business API</strong>.</li>
        </ul>
      </section>

      <section className="mb-10 text-pretty">
        <h2 className="text-xl font-bold text-slate-800 mb-4 border-b border-slate-100 pb-2">3. Finalidad del Tratamiento</h2>
        <p className="mb-4">Los datos recopilados se utilizan exclusivamente para:</p>
        <ul className="list-disc pl-5 mt-2 space-y-3">
          <li>Visualizar y categorizar sus gastos personales y compartidos.</li>
          <li>Enviar alertas de gastos y recordatorios vía WhatsApp.</li>
          <li>Mejorar la experiencia de usuario y la precisión de la categorización mediante inteligencia artificial.</li>
        </ul>
      </section>

      <section className="mb-10 text-pretty">
        <h2 className="text-xl font-bold text-slate-800 mb-4 border-b border-slate-100 pb-2">4. Derechos ARCO</h2>
        <p className="mb-4">
          Usted tiene derecho a <strong className="text-slate-900">Acceder, Rectificar, Cancelar u Oponerse (ARCO)</strong> al tratamiento de sus datos personales en cualquier momento. 
          Para ejercer estos derechos, puede:
        </p>
        <ul className="list-disc pl-5 mt-2 space-y-3">
          <li>Utilizar las herramientas de configuración dentro de la aplicación.</li>
          <li>Enviar una solicitud formal a <strong className="text-indigo-600 underline">rafaellabra96@gmail.com</strong>.</li>
        </ul>
      </section>

      <section className="mb-10 text-pretty">
        <h2 className="text-xl font-bold text-slate-800 mb-4 border-b border-slate-100 pb-2">5. Seguridad de los Datos</h2>
        <p className="mb-4">
          Implementamos medidas de seguridad técnicas y organizativas, incluyendo cifrado SSL y almacenamiento seguro en <strong className="text-indigo-600">Supabase</strong>, 
          para prevenir el acceso no autorizado o la pérdida de datos.
        </p>
      </section>

      <section className="text-pretty">
        <h2 className="text-xl font-bold text-slate-800 mb-4 border-b border-slate-100 pb-2">6. Contacto</h2>
        <p className="mb-4">
          Para cualquier duda sobre esta política, puede contactar al responsable: <br />
          <strong className="text-slate-900">Rafael Labra</strong><br />
          Email: <span className="text-indigo-600">rafaellabra96@gmail.com</span>
        </p>
      </section>
    </article>
  );
}
