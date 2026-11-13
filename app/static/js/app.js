/* ==========================================================================
   BabyTrack - Lógica Cliente e Interactividad Reactiva
   ========================================================================== */

window.BabyTrack = {
  getActiveParent() {
    return localStorage.getItem('babytrack_active_parent') || 'MAMA';
  },

  setActiveParent(role) {
    localStorage.setItem('babytrack_active_parent', role);
    window.dispatchEvent(new CustomEvent('parent-changed', { detail: role }));
  },

  openFileViewer(attachment, studyTitle = '', allAttachments = null) {
    const list = Array.isArray(allAttachments) && allAttachments.length > 0
      ? allAttachments
      : [attachment];
    const index = Math.max(0, list.findIndex(a => a.id === attachment.id));
    window.dispatchEvent(new CustomEvent('open-file-viewer', {
      detail: {
        attachments: list,
        index: index,
        studyTitle: studyTitle
      }
    }));
  },

  openConsultationMode() {
    window.dispatchEvent(new CustomEvent('open-consultation-mode'));
  },

  openPinModal() {
    window.dispatchEvent(new CustomEvent('open-pin-modal'));
  },

  async setGenderTheme(genderMode) {
    try {
      const response = await fetch('/api/v1/settings/gender-theme', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ genderMode: genderMode })
      });

      if (!response.ok) {
        throw new Error('Error al actualizar el tema');
      }

      const data = await response.json();
      document.documentElement.setAttribute('data-theme', data.genderMode);
      this.fireCelebration(data.genderMode);

      setTimeout(() => {
        window.location.reload();
      }, 700);
    } catch (error) {
      console.error('Error:', error);
      alert('No se pudo cambiar el tema: ' + error.message);
    }
  },

  fireCelebration(mode) {
    if (typeof confetti !== 'function') return;

    let colors = ['#5F8D75', '#E2A03F', '#FAF7F2'];
    if (mode === 'BOY') {
      colors = ['#3B82F6', '#60A5FA', '#93C5FD', '#FFFFFF', '#6366F1'];
    } else if (mode === 'GIRL') {
      colors = ['#EC4899', '#F472B6', '#FBCFE8', '#FFD700', '#A855F7'];
    }

    confetti({
      particleCount: 100,
      spread: 70,
      origin: { y: 0.6 },
      colors: colors
    });

    setTimeout(() => {
      confetti({ particleCount: 50, angle: 60, spread: 55, origin: { x: 0 }, colors: colors });
      confetti({ particleCount: 50, angle: 120, spread: 55, origin: { x: 1 }, colors: colors });
    }, 250);
  },

  async calibrateObstetric(event) {
    event.preventDefault();
    const form = event.target;
    const weeks = parseInt(form.weeks.value, 10);
    const days = parseInt(form.days.value, 10);
    const dueDate = form.dueDate.value;

    const payload = {};
    if (dueDate) payload.dueDate = dueDate;
    if (!isNaN(weeks) && !isNaN(days)) {
      payload.currentWeeks = weeks;
      payload.currentDays = days;
    }

    try {
      const response = await fetch('/api/v1/settings/obstetric', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });

      if (!response.ok) {
        throw new Error('Error al calibrar el embarazo');
      }

      window.location.reload();
    } catch (err) {
      alert('Error: ' + err.message);
    }
  }
};

// Registro de Service Worker PWA
if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/static/sw.js').catch(() => {});
  });
}
