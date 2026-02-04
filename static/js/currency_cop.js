function formatCop(value) {
  if (value === null || value === undefined) return '';
  let s = String(value).trim();
  // Quitar prefijos y espacios
  s = s.replace(/cop/ig, '').replace(/\$/g, '').replace(/\s+/g, '');
  // Si trae decimales al final ("4000.00" o "1.234,50"), elimínalos para no inflar miles
  s = s.replace(/[\.,]\d{1,2}$/,'');
  // Mantener solo dígitos (miles con punto se conservan como dígitos)
  const digits = s.replace(/[^0-9]/g, '');
  if (!digits) return '';
  const n = parseInt(digits, 10) || 0;
  try {
    return 'COP $' + n.toLocaleString('es-CO');
  } catch (e) {
    // Fallback si toLocaleString falla
    return 'COP $' + String(n).replace(/\B(?=(\d{3})+(?!\d))/g, '.');
  }
}

function initCopInputs() {
  const inputs = document.querySelectorAll('.money-input');
  inputs.forEach((input) => {
    // Formatear valor inicial si lo hay
    if (input.value) {
      input.value = formatCop(input.value);
    }

    input.addEventListener('input', () => {
      input.value = formatCop(input.value);
    });

    input.addEventListener('blur', () => {
      input.value = formatCop(input.value);
    });
  });
}

// Auto-init si se carga este script después del DOM
document.addEventListener('DOMContentLoaded', () => {
  if (typeof initCopInputs === 'function') {
    initCopInputs();
  }
});