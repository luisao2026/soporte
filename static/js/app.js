/*
 * Ventana de confirmación propia del sistema (reemplaza al confirm() del navegador).
 *
 * Uso en cualquier botón de un formulario:
 *   <button data-confirmar="¿Desactivar a Juan Pérez?"      ← mensaje (obligatorio)
 *           data-titulo="Desactivar usuario"                ← título (opcional)
 *           data-boton="Sí, desactivar"                     ← texto del botón (opcional)
 *           data-tipo="peligro">                            ← peligro | aviso | exito | info (opcional)
 */
(function () {
  const TIPOS = {
    peligro: { icono: "bi-exclamation-octagon", clase: "peligro", boton: "btn-danger" },
    aviso: { icono: "bi-exclamation-triangle", clase: "aviso", boton: "btn-warning" },
    exito: { icono: "bi-check2-circle", clase: "exito", boton: "btn-istam" },
    info: { icono: "bi-question-circle", clase: "info", boton: "btn-istam" },
  };

  const modalEl = document.getElementById("modal-confirmar");
  if (!modalEl || !window.bootstrap) return;
  const modal = bootstrap.Modal.getOrCreateInstance(modalEl);
  const $ = (sel) => modalEl.querySelector(sel);
  let pendiente = null; // { form, boton }

  document.addEventListener("submit", function (e) {
    const boton = e.submitter;
    const msg = (boton && boton.dataset.confirmar) || e.target.dataset.confirmar;
    if (!msg) return;
    if (e.target.dataset.confirmado === "1") { // ya se aceptó en la ventana
      delete e.target.dataset.confirmado;
      return;
    }
    e.preventDefault();
    const datos = Object.assign({}, e.target.dataset, boton ? boton.dataset : {});
    const tipo = TIPOS[datos.tipo] || TIPOS.info;

    $(".confirmar-icono").className = "confirmar-icono " + tipo.clase;
    $(".confirmar-icono i").className = "bi " + tipo.icono;
    $(".confirmar-titulo").textContent = datos.titulo || "Confirmar acción";
    $(".confirmar-mensaje").textContent = msg;
    const aceptar = $(".confirmar-aceptar");
    aceptar.className = "btn confirmar-aceptar px-4 " + tipo.boton;
    aceptar.textContent = datos.boton || "Aceptar";

    pendiente = { form: e.target, boton: boton };
    modal.show();
  }, true);

  $(".confirmar-aceptar").addEventListener("click", function () {
    if (!pendiente) return;
    const { form, boton } = pendiente;
    pendiente = null;
    modal.hide();
    form.dataset.confirmado = "1";
    form.requestSubmit(boton || undefined); // conserva el botón que se presionó
  });

  modalEl.addEventListener("shown.bs.modal", () => $(".confirmar-aceptar").focus());
  modalEl.addEventListener("hidden.bs.modal", () => { pendiente = null; });
})();

// Evita doble envío de formularios
document.addEventListener("submit", function (e) {
  if (e.defaultPrevented) return;
  const b = e.submitter;
  if (b && !b.formTarget) setTimeout(() => (b.disabled = true), 0);
});

// Los mensajes de éxito se ocultan solos después de 6 segundos
document.querySelectorAll(".alert-success.alert-dismissible").forEach(function (a) {
  setTimeout(() => window.bootstrap && bootstrap.Alert.getOrCreateInstance(a).close(), 6000);
});
