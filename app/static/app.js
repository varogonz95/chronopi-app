const state = {
  payload: null,
  countdownInterval: null,
};

const STATUS_PRESETS = {
  available: {
    badge: 'CURRENT STATE',
    heading: 'Available',
    actions: ['Open Door', 'Quick Questions OK'],
    sectionTitle: 'Upcoming Events',
    sectionCta: 'View Calendar',
    showHeroFooter: false,
    showConnectPanel: false,
    showList: true,
    showStatusSwitch: false,
  },
  busy: {
    badge: 'CURRENTLY ACTIVE',
    heading: 'Busy',
    actions: ['Do Not Disturb', 'Urgent Only'],
    sectionTitle: 'Upcoming Next',
    sectionCta: 'View Calendar',
    showHeroFooter: true,
    showConnectPanel: false,
    showList: true,
    showStatusSwitch: false,
  },
  focus: {
    badge: 'CURRENT STATE',
    heading: 'Focusing',
    subtitle: 'Deep work mode',
    actions: ['Extremely Silent', 'Messaging Only'],
    sectionTitle: 'Coming Up',
    sectionCta: 'Next 24 hours',
    showHeroFooter: false,
    showConnectPanel: false,
    showList: true,
    showStatusSwitch: false,
  },
  ooo: {
    badge: 'CURRENT STATE',
    heading: 'Out of Office',
    actions: ['Away from Desk', 'Email for response'],
    sectionTitle: 'Update Status',
    sectionCta: '',
    showHeroFooter: false,
    showConnectPanel: false,
    showList: false,
    showStatusSwitch: true,
  },
  connect: {
    badge: 'SETUP',
    heading: 'Connect Your World',
    subtitle: 'Scan the QR code to sync your calendars and set your sanctuary status.',
    actions: [],
    sectionTitle: 'Providers',
    sectionCta: '',
    showHeroFooter: false,
    showConnectPanel: true,
    showList: false,
    showStatusSwitch: false,
  },
};

function byId(id) {
  return document.getElementById(id);
}

function setVisibility(id, visible) {
  byId(id).classList.toggle('hidden', !visible);
}

function hasConnectedProvider(providers) {
  return (providers || []).some((provider) => provider.connected);
}

function looksLikeOutOfOffice(payload) {
  const haystack = [payload.heading, payload.subheading, payload.currentTitle, payload.currentSubtitle]
    .filter(Boolean)
    .join(' ')
    .toLowerCase();
  return /(out of office|\booo\b|vacation|pto|away)/.test(haystack);
}

function inferStatus(payload) {
  if (!hasConnectedProvider(payload.providers)) {
    return 'available';
  }
  if (payload.currentEvent && payload.currentEvent.kind === 'focus') {
    return 'focus';
  }
  if (looksLikeOutOfOffice(payload)) {
    return 'ooo';
  }
  if (payload.currentEvent) {
    return 'busy';
  }
  return 'available';
}

function formatClockLocal(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return '--:--';
  }
  return date.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
}

function buildBusyMeta(payload) {
  if (!payload.currentEvent) {
    return payload.currentRange || '';
  }
  const endLabel = formatClockLocal(payload.currentEvent.endsAt);
  return `Ends at ${endLabel} (${payload.remainingMinutes}m left)`;
}

function resolveHeroText(payload, status) {
  const preset = STATUS_PRESETS[status];
  const heading = preset.heading || payload.heading;
  let subtitle = payload.subheading;

  if (status === 'connect') {
    subtitle = preset.subtitle;
  }
  if (status === 'focus' && preset.subtitle) {
    subtitle = preset.subtitle;
  }
  if (status === 'available' && payload.currentRange) {
    subtitle = payload.currentRange;
  }
  if (status === 'ooo') {
    subtitle = payload.subheading || 'Back soon';
  }

  return {
    heading,
    subtitle,
    meta: status === 'busy' ? buildBusyMeta(payload) : (payload.currentSubtitle || ''),
  };
}

function renderActionRow(status) {
  const row = byId('actionRow');
  row.innerHTML = '';
  const preset = STATUS_PRESETS[status];
  for (const label of preset.actions) {
    const chip = document.createElement('button');
    chip.type = 'button';
    chip.className = 'action-chip inert-action';
    chip.setAttribute('aria-disabled', 'true');
    chip.textContent = label;
    row.appendChild(chip);
  }
}

function upcomingDate(baseDate, index) {
  const clone = new Date(baseDate);
  clone.setDate(clone.getDate() + index);
  const month = clone.toLocaleString([], { month: 'short' }).toUpperCase();
  const day = String(clone.getDate());
  return { month, day };
}

function renderUpcoming(payload, status) {
  const upcoming = payload.upcoming || [];
  const list = byId('upcomingList');
  list.innerHTML = '';
  const template = byId('upcomingTemplate');
  const seedDate = payload.generatedAt ? new Date(payload.generatedAt) : new Date();

  if (!upcoming.length) {
    const empty = document.createElement('p');
    empty.className = 'upcoming-subtitle';
    empty.textContent = status === 'connect'
      ? 'Connect at least one provider to populate your event timeline.'
      : 'No upcoming events in the current lookahead window.';
    list.appendChild(empty);
    return;
  }

  upcoming.forEach((item, index) => {
    const fragment = template.content.cloneNode(true);
    const date = upcomingDate(seedDate, index);
    fragment.querySelector('.date-month').textContent = date.month;
    fragment.querySelector('.date-day').textContent = date.day;
    fragment.querySelector('.upcoming-title').textContent = item.title;
    fragment.querySelector('.upcoming-range').textContent = item.range;
    fragment.querySelector('.upcoming-subtitle').textContent = item.subtitle;
    fragment.querySelector('.upcoming-item').style.animationDelay = `${120 + index * 80}ms`;
    list.appendChild(fragment);
  });
}

function renderProviders(providers) {
  const host = byId('providerStatus');
  host.innerHTML = '';
  for (const provider of providers) {
    const pill = document.createElement('span');
    pill.className = `provider-pill ${provider.connected ? 'is-connected' : ''}`.trim();
    pill.textContent = provider.displayName;
    host.appendChild(pill);
  }
}

function applyStatusLayout(payload, status) {
  const preset = STATUS_PRESETS[status];
  const heroText = resolveHeroText(payload, status);
  document.body.dataset.status = status;
  byId('statusBadgeText').textContent = preset.badge;
  byId('heading').textContent = heroText.heading;
  byId('subheading').textContent = heroText.subtitle;
  byId('heroMeta').textContent = heroText.meta;
  byId('clockMeta').textContent = `${payload.clock} • ${payload.dateLabel}`;
  byId('upcomingHeading').textContent = preset.sectionTitle;
  byId('calendarCta').textContent = preset.sectionCta;

  setVisibility('heroFooter', preset.showHeroFooter);
  setVisibility('connectPanel', preset.showConnectPanel);
  setVisibility('listSection', preset.showList);
  setVisibility('statusSwitch', preset.showStatusSwitch);

  byId('primaryAction').textContent = 'End Early';
  byId('iconActionGlyph').textContent = '✎';
  renderActionRow(status);
}

function applyPayload(payload) {
  state.payload = payload;
  const status = inferStatus(payload);
  applyStatusLayout(payload, status);
  renderUpcoming(payload, status);
  renderProviders(payload.providers || []);
  byId('errorBar').textContent = (payload.errors || []).join(' | ');
}

function updateCountdown() {
  if (!state.payload) {
    return;
  }

  const status = inferStatus(state.payload);
  if (!state.payload.currentEvent || status !== 'busy') {
    return;
  }

  const now = new Date();
  const end = new Date(state.payload.currentEvent.endsAt);
  const remainingSeconds = Math.max((end - now) / 1000, 0);
  state.payload.remainingMinutes = Math.ceil(remainingSeconds / 60);
  byId('heroMeta').textContent = buildBusyMeta(state.payload);
}

async function fetchStatus() {
  const response = await fetch('/api/status', { cache: 'no-store' });
  if (!response.ok) {
    throw new Error(`Status request failed with ${response.status}`);
  }
  const payload = await response.json();
  applyPayload(payload);
}

async function refreshLoop() {
  try {
    await fetchStatus();
  } catch (error) {
    byId('errorBar').textContent = error.message;
  }
}

function enableDragScroll() {
  const root = byId('scrollRoot');
  let dragging = false;
  let startY = 0;
  let originScroll = 0;

  root.addEventListener('pointerdown', (event) => {
    if (event.pointerType === 'mouse' && event.button !== 0) {
      return;
    }
    dragging = true;
    startY = event.clientY;
    originScroll = root.scrollTop;
    root.classList.add('is-dragging');
    if (typeof root.setPointerCapture === 'function') {
      root.setPointerCapture(event.pointerId);
    }
  });

  root.addEventListener('pointermove', (event) => {
    if (!dragging) {
      return;
    }
    root.scrollTop = originScroll - (event.clientY - startY);
  });

  const finish = (event) => {
    if (!dragging) {
      return;
    }
    dragging = false;
    root.classList.remove('is-dragging');
    if (typeof root.releasePointerCapture === 'function' && root.hasPointerCapture(event.pointerId)) {
      root.releasePointerCapture(event.pointerId);
    }
  };

  root.addEventListener('pointerup', finish);
  root.addEventListener('pointercancel', finish);
}

window.addEventListener('DOMContentLoaded', () => {
  enableDragScroll();
  if (window.APP_BOOTSTRAP.connectedProvider) {
    byId('errorBar').textContent = `${window.APP_BOOTSTRAP.connectedProvider} connected.`;
  }
  refreshLoop();
  window.setInterval(refreshLoop, 30000);
  state.countdownInterval = window.setInterval(updateCountdown, 1000);
});
