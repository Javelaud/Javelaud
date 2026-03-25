/* ==========================================
   JAVELAUD — Création SASU
   Multi-step form + UI helpers
   ========================================== */

// ==========================================
// Multi-step form (Tailwind version)
// ==========================================

function nextStep(step) {
  const current = document.querySelector('.step-panel.active');
  if (!current) return;

  // Validate current step fields
  const required = current.querySelectorAll('input[required], select[required], textarea[required]');
  let valid = true;
  required.forEach(el => {
    if (!el.value.trim()) {
      el.classList.add('border-red-400', 'bg-red-50');
      el.classList.remove('border-slate-200', 'bg-slate-50');
      valid = false;
    } else {
      el.classList.remove('border-red-400', 'bg-red-50');
      el.classList.add('border-slate-200', 'bg-slate-50');
    }
  });

  // Radio group validation for civilite
  const civiliteRadios = current.querySelectorAll('input[name="civilite"]');
  if (civiliteRadios.length > 0) {
    const checked = current.querySelector('input[name="civilite"]:checked');
    if (!checked) {
      valid = false;
      const firstRadioLabel = civiliteRadios[0].closest('label');
      if (firstRadioLabel) firstRadioLabel.classList.add('ring-2', 'ring-red-400');
    }
  }

  if (!valid) {
    showToast('Veuillez remplir tous les champs obligatoires.', 'error');
    const firstInvalid = current.querySelector('.border-red-400');
    if (firstInvalid) firstInvalid.focus();
    return;
  }

  // Transition to next step
  current.classList.remove('active');
  const next = document.getElementById(`step-${step}`);
  if (next) {
    next.classList.add('active');
    updateStepIndicator(step);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  if (step === 4) buildRecap();
}

function prevStep(step) {
  const current = document.querySelector('.step-panel.active');
  if (current) current.classList.remove('active');
  const prev = document.getElementById(`step-${step}`);
  if (prev) {
    prev.classList.add('active');
    updateStepIndicator(step);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }
}

function updateStepIndicator(activeStep) {
  document.querySelectorAll('.step-indicator-item').forEach((item) => {
    const step = parseInt(item.dataset.step);
    const numEl = item.querySelector('.step-num');
    if (!numEl) return;

    if (step < activeStep) {
      // Completed
      item.classList.add('done');
      item.classList.remove('active');
      numEl.innerHTML = `<svg class="w-4 h-4 text-white mx-auto" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M5 13l4 4L19 7"/>
      </svg>`;
    } else if (step === activeStep) {
      item.classList.add('active');
      item.classList.remove('done');
      numEl.textContent = step;
    } else {
      item.classList.remove('active', 'done');
      numEl.textContent = step;
    }
  });
}

// ==========================================
// Recap builder
// ==========================================

function buildRecap() {
  const container = document.getElementById('recap-content');
  if (!container) return;

  const get = (name) => {
    const el = document.querySelector(`[name="${name}"]`);
    if (!el) return '';
    if (el.type === 'radio') {
      const checked = document.querySelector(`[name="${name}"]:checked`);
      return checked ? checked.value : '';
    }
    return el.value || '';
  };

  const sections = [
    {
      title: 'Dirigeant',
      rows: [
        ['Civilité', get('civilite')],
        ['Prénom', get('prenom')],
        ['Nom', get('nom')],
        ['Nom de naissance', get('nom_jeune_fille')],
        ['Date de naissance', get('date_naissance')],
        ['Lieu de naissance', `${get('lieu_naissance')} (${get('departement_naissance')})`],
        ['Nationalité', get('nationalite')],
        ['Situation', get('situation_matrimoniale')],
      ]
    },
    {
      title: 'Adresse',
      rows: [
        ['Rue', get('adresse_rue')],
        ['Code postal', get('adresse_cp')],
        ['Ville', get('adresse_ville')],
        ['Pays', get('adresse_pays')],
      ]
    },
    {
      title: 'Filiation',
      rows: [
        ['Père', `${get('prenom_pere')} ${get('nom_pere')}`],
        ['Mère', `${get('prenom_mere_naissance')} ${get('nom_mere')}`],
      ]
    },
    {
      title: 'Société',
      rows: [
        ['Dénomination', get('denomination_sociale')],
        ['Siège', `${get('siege_social_rue')}, ${get('siege_social_cp')} ${get('siege_social_ville')}`],
        ['Capital', get('capital_social') ? `${get('capital_social')} €` : ''],
        ['Durée', get('duree') ? `${get('duree')} ans` : ''],
        ['Clôture', get('date_cloture_exercice')],
        ['Régime fiscal', get('regime_fiscal')],
      ]
    }
  ];

  let html = '';
  sections.forEach(section => {
    const validRows = section.rows.filter(([, v]) => v && v.trim() && v.trim() !== ' ()');
    if (!validRows.length) return;
    html += `<div>
      <h4 class="text-xs font-semibold text-gold-700 uppercase tracking-wider mb-3">${section.title}</h4>
      <div class="space-y-1.5">`;
    validRows.forEach(([label, value]) => {
      html += `<div class="flex gap-3">
        <span class="text-xs text-slate-400 w-28 flex-shrink-0">${label}</span>
        <span class="text-xs font-medium text-slate-900">${value}</span>
      </div>`;
    });
    html += '</div></div>';
  });

  container.innerHTML = html;
}

// ==========================================
// Toast notifications
// ==========================================

function showToast(message, type = 'info') {
  const existing = document.getElementById('toast-notification');
  if (existing) existing.remove();

  const colors = {
    error: 'bg-red-600',
    success: 'bg-emerald-600',
    info: 'bg-slate-800'
  };

  const toast = document.createElement('div');
  toast.id = 'toast-notification';
  toast.className = `fixed bottom-6 right-6 z-50 ${colors[type]} text-white text-sm font-medium px-5 py-3 rounded-xl shadow-lg flex items-center gap-3 transition-all`;
  toast.innerHTML = `<span>${message}</span>
    <button onclick="this.parentElement.remove()" class="text-white/60 hover:text-white ml-2 text-lg leading-none">&times;</button>`;
  document.body.appendChild(toast);

  setTimeout(() => { if (toast.parentNode) toast.remove(); }, 4000);
}

// ==========================================
// DOM ready
// ==========================================

document.addEventListener('DOMContentLoaded', () => {

  // Clear validation styling on input
  document.querySelectorAll('input, select, textarea').forEach(el => {
    el.addEventListener('input', () => {
      if (el.value.trim()) {
        el.classList.remove('border-red-400', 'bg-red-50');
        el.classList.add('border-slate-200');
      }
    });
  });

  // Auto-dismiss flash alerts
  document.querySelectorAll('[data-auto-dismiss]').forEach(el => {
    setTimeout(() => {
      el.style.transition = 'opacity 0.4s';
      el.style.opacity = '0';
      setTimeout(() => el.remove(), 400);
    }, 5000);
  });

});
