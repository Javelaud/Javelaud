/* ==========================================
   JAVELAUD — Création SASU : JS
   ========================================== */

// ==========================================
// Multi-step form navigation
// ==========================================

function nextStep(step) {
  const current = document.querySelector('.form-step.active');
  const currentNum = parseInt(current.id.replace('step-', ''));

  // Validate current step
  const inputs = current.querySelectorAll('input[required], select[required], textarea[required]');
  let valid = true;
  inputs.forEach(input => {
    if (!input.value.trim()) {
      input.style.borderColor = '#dc2626';
      input.style.boxShadow = '0 0 0 3px rgba(220,38,38,0.1)';
      valid = false;
    } else {
      input.style.borderColor = '';
      input.style.boxShadow = '';
    }
  });

  if (!valid) {
    const firstInvalid = current.querySelector('input[required]:invalid, input[required][value=""], select[required]');
    if (firstInvalid) firstInvalid.focus();
    showStepError('Veuillez remplir tous les champs obligatoires.');
    return;
  }

  clearStepError();

  // Move to next step
  current.classList.remove('active');
  const next = document.getElementById(`step-${step}`);
  if (next) {
    next.classList.add('active');
    updateStepIndicator(step);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  // Build recap on step 4
  if (step === 4) buildRecap();
}

function prevStep(step) {
  const current = document.querySelector('.form-step.active');
  current.classList.remove('active');
  const prev = document.getElementById(`step-${step}`);
  if (prev) {
    prev.classList.add('active');
    updateStepIndicator(step);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }
}

function updateStepIndicator(activeStep) {
  document.querySelectorAll('.step').forEach((step, index) => {
    const stepNum = index + 1;
    step.classList.remove('active', 'completed');
    if (stepNum < activeStep) step.classList.add('completed');
    else if (stepNum === activeStep) step.classList.add('active');
  });
}

function showStepError(msg) {
  let el = document.getElementById('step-error');
  if (!el) {
    el = document.createElement('div');
    el.id = 'step-error';
    el.className = 'alert alert-error';
    el.style.marginTop = '12px';
    const active = document.querySelector('.form-step.active');
    active.querySelector('.form-actions').before(el);
  }
  el.textContent = msg;
}

function clearStepError() {
  const el = document.getElementById('step-error');
  if (el) el.remove();
}

// ==========================================
// Recap builder
// ==========================================

function buildRecap() {
  const container = document.getElementById('recap-content');
  if (!container) return;

  const getValue = (name) => {
    const el = document.querySelector(`[name="${name}"]`);
    return el ? el.value : '';
  };

  const sections = [
    {
      title: 'Dirigeant',
      rows: [
        ['Civilité', getValue('civilite')],
        ['Nom', getValue('nom')],
        ['Prénom', getValue('prenom')],
        ['Nom de naissance', getValue('nom_jeune_fille')],
        ['Date de naissance', getValue('date_naissance')],
        ['Lieu de naissance', `${getValue('lieu_naissance')} (${getValue('departement_naissance')})`],
        ['Nationalité', getValue('nationalite')],
        ['Situation matrimoniale', getValue('situation_matrimoniale')],
      ]
    },
    {
      title: 'Adresse',
      rows: [
        ['Adresse', getValue('adresse_rue')],
        ['Code postal', getValue('adresse_cp')],
        ['Ville', getValue('adresse_ville')],
        ['Pays', getValue('adresse_pays')],
      ]
    },
    {
      title: 'Filiation',
      rows: [
        ['Père', `${getValue('prenom_pere')} ${getValue('nom_pere')}`],
        ['Mère (nom naissance)', `${getValue('prenom_mere_naissance')} ${getValue('nom_mere')}`],
      ]
    },
    {
      title: 'Société',
      rows: [
        ['Dénomination', getValue('denomination_sociale')],
        ['Siège social', `${getValue('siege_social_rue')}, ${getValue('siege_social_cp')} ${getValue('siege_social_ville')}`],
        ['Capital social', `${getValue('capital_social')} €`],
        ['Durée', `${getValue('duree')} ans`],
        ['Clôture exercice', getValue('date_cloture_exercice')],
        ['Régime fiscal', getValue('regime_fiscal')],
      ]
    }
  ];

  let html = '';
  sections.forEach(section => {
    html += `<div class="recap-section">`;
    html += `<h4>${section.title}</h4>`;
    section.rows.forEach(([label, value]) => {
      if (value && value.trim()) {
        html += `<div class="recap-row">
          <span class="recap-label">${label}</span>
          <span class="recap-value">${value}</span>
        </div>`;
      }
    });
    html += '</div>';
  });

  container.innerHTML = html;
}

// ==========================================
// Input validation feedback
// ==========================================

document.addEventListener('DOMContentLoaded', () => {
  // Remove red border on input
  document.querySelectorAll('input, select, textarea').forEach(el => {
    el.addEventListener('input', () => {
      if (el.value.trim()) {
        el.style.borderColor = '';
        el.style.boxShadow = '';
      }
    });
  });

  // Auto-dismiss alerts after 5s
  const alerts = document.querySelectorAll('.alert');
  alerts.forEach(alert => {
    setTimeout(() => {
      alert.style.transition = 'opacity 0.5s';
      alert.style.opacity = '0';
      setTimeout(() => alert.remove(), 500);
    }, 5000);
  });

  // File input label update
  document.querySelectorAll('.file-input-label input[type="file"]').forEach(input => {
    input.addEventListener('change', () => {
      const display = input.closest('.file-input-wrapper').querySelector('.file-name-display');
      if (display && input.files.length > 0) {
        display.textContent = input.files[0].name;
      }
    });
  });
});
