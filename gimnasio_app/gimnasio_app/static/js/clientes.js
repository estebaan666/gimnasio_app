document.addEventListener("DOMContentLoaded", () => {
    const searchInput = document.getElementById("searchInput");
    const clickablePhotos = document.querySelectorAll('.js-open-cliente');
    const medidasToggle = document.getElementById('toggleMedidas');
    const medidasBox = document.getElementById('medidasBox');

    /* 🔎 Filtro de búsqueda */
    if (searchInput) {
        searchInput.addEventListener("keyup", function() {
            const filter = this.value.toLowerCase();
            const cards = document.querySelectorAll("#clientCards .client-card");
            cards.forEach(card => {
                const name = card.dataset.nombre.toLowerCase();
                card.style.display = name.includes(filter) ? "flex" : "none";
            });
        });
    }

    /* 👆 Abrir modal desde data-cliente sin inline JS */
    clickablePhotos.forEach(el => {
        el.addEventListener('click', () => {
            const json = el.getAttribute('data-cliente');
            try {
                const cliente = JSON.parse(json);
                showDetails(cliente);
            } catch (e) {
                console.error('No se pudo leer datos del cliente', e);
            }
        });
    });

    // Toggle de medidas en el modal
    if (medidasToggle && medidasBox) {
        medidasToggle.addEventListener('click', () => {
            const visible = medidasBox.style.display === 'block';
            medidasBox.style.display = visible ? 'none' : 'block';
        });
    }
});

/* 📌 Mostrar modal con datos */
function showDetails(cliente) {
    document.getElementById("modalNombre").textContent = cliente.nombre + " " + cliente.apellido;
    document.getElementById("modalIdentificacion").textContent = cliente.identificacion || "N/D";
    document.getElementById("modalGenero").textContent = cliente.genero || "N/D";
    document.getElementById("modalNacimiento").textContent = formatDateToDMY(cliente.fecha_nacimiento);
    document.getElementById("modalTelefono").textContent = cliente.telefono || "N/D";
    document.getElementById("modalEmail").textContent = cliente.email || "N/D";
    document.getElementById("modalDireccion").textContent = cliente.direccion || "N/D";
    document.getElementById("modalEnfermedades").textContent = cliente.enfermedades || "N/D";
    document.getElementById("modalAlergias").textContent = cliente.alergias || "N/D";
    document.getElementById("modalFracturas").textContent = cliente.fracturas || "N/D";
    document.getElementById("modalObservaciones").textContent = cliente.observaciones_medicas || "N/D";

    // Membresía y pagos
    const memb = document.getElementById("modalMembresia");
    if (memb) memb.textContent = cliente.tipo_membresia || "N/D";
    const prox = document.getElementById("modalProximoPago");
    if (prox) prox.textContent = cliente.proximo_pago ? formatDateToDMY(cliente.proximo_pago) : "N/D";
    const est = document.getElementById("modalEstadoPago");
    if (est) est.textContent = cliente.estado_pago || "N/D";

    // 📸 Foto con fallback
    document.getElementById("modalFoto").src = cliente.foto_url || "/static/img/default-user.png";

    const modal = document.getElementById("clientModal");
    modal.dataset.clienteId = cliente.id_cliente;
    modal.style.display = "flex";

    // Medidas corporales (sección colapsable)
    const medidas = cliente.medidas || {};
    setText('mPeso', fmt(medidas.peso));
    setText('mAltura', fmt(medidas.altura));
    setText('mImc', fmt(medidas.imc));
    setText('mCintura', fmt(medidas.cintura));
    setText('mPecho', fmt(medidas.pecho));
    setText('mBrazo', fmt(medidas.brazo));
    setText('mPierna', fmt(medidas.pierna));
    setText('mObsMedidas', medidas.observaciones || 'N/D');

    // Ocultar medidas por defecto para no saturar
    const box = document.getElementById('medidasBox');
    if (box) box.style.display = 'none';

    // Animación
    const modalContent = modal.querySelector(".modal-content");
    modalContent.style.animation = "none";
    modalContent.offsetHeight;
    modalContent.style.animation = "zoomIn 0.4s ease forwards";
}

// Formatear fecha a DD/MM/YYYY con tolerancia a varios formatos
function formatDateToDMY(val){
    try{
        if(!val) return "N/D";
        const d = new Date(val);
        if(!isNaN(d.getTime())){
            const dd = String(d.getDate()).padStart(2,'0');
            const mm = String(d.getMonth()+1).padStart(2,'0');
            const yyyy = d.getFullYear();
            return `${dd}/${mm}/${yyyy}`;
        }
        // Intento manual: formatos tipo YYYY-MM-DD o DD/MM/YYYY
        const parts = String(val).split(/[-/ T]/).filter(Boolean);
        if(parts.length >= 3){
            // Si empieza por 4 dígitos asumo YYYY-MM-DD
            if(parts[0].length === 4){
                const yyyy = parts[0];
                const mm = parts[1].padStart(2,'0');
                const dd = parts[2].padStart(2,'0');
                return `${dd}/${mm}/${yyyy}`;
            }
            // Si termina con 4 dígitos asumo DD/MM/YYYY
            if(parts[2].length === 4){
                const dd = parts[0].padStart(2,'0');
                const mm = parts[1].padStart(2,'0');
                const yyyy = parts[2];
                return `${dd}/${mm}/${yyyy}`;
            }
        }
        return String(val);
    }catch(e){
        return "N/D";
    }
}

// Utilidades
function fmt(v){
    const n = parseFloat(v);
    return (!isNaN(n)) ? n.toFixed(2) : (v ? String(v) : 'N/D');
}
function setText(id, val){
    const el = document.getElementById(id);
    if (el) el.textContent = val ?? 'N/D';
}

/* ❌ Cerrar modal */
function closeModal() {
    document.getElementById("clientModal").style.display = "none";
}

/* ✏️ Editar cliente */
function editClient() {
    const id = document.getElementById("clientModal").dataset.clienteId;
    if (id) {
        window.location.href = `/clientes/editar/${id}`;
    }
}

/* 🗑️ Eliminar cliente */
function deleteClient() {
    const id = document.getElementById("clientModal").dataset.clienteId;
    if (id && confirm("¿Seguro que quieres eliminar este cliente?")) {
        fetch(`/clientes/eliminar/${id}`, {
            method: "POST"
        }).then(() => {
            window.location.reload();
        }).catch(err => alert("Error al eliminar cliente: " + err));
    }
}

/* Exponer funciones al HTML */
window.showDetails = showDetails;
window.closeModal = closeModal;
window.editClient = editClient;
window.deleteClient = deleteClient;
