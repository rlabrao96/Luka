export function PrivacySection() {
  return (
    <div className="bg-white rounded-xl border border-slate-100 shadow-[0_1px_3px_rgba(0,0,0,0.03)] p-5">
      <h3 className="text-sm font-semibold text-slate-500 uppercase tracking-wider mb-4">
        Privacidad de Datos
      </h3>
      <div className="space-y-2 text-sm text-slate-500 leading-relaxed">
        <p>
          Luka procesa tus notificaciones bancarias para categorizar transacciones.
          Los emails se eliminan automáticamente dentro de 24 horas.
        </p>
        <p>
          Nunca almacenamos números de tarjeta, contraseñas bancarias ni credenciales
          de acceso a tu banco.
        </p>
        <p>
          Puedes eliminar tu cuenta y todos tus datos en cualquier momento desde esta
          página.
        </p>
      </div>
    </div>
  );
}
