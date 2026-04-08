const state = {
  payload: null,
  countdownInterval: null,
};

function byId(id) {
  return document.getElementById(id);
}

function formatRangeForNext(nextEvent) {
  return `Next: ${nextEvent.title} - ${nextEvent.range}`;
}

function updateRing(progress) {
  byId('ring').style.setProperty('--progress', String(progress));
}

function renderUpcoming(upcoming) {
  const list = byId('upcomingList');
  list.innerHTML = '';
  const template = byId('upcomingTemplate');

  if (!upcoming.length) {
    const empty = document.createElement('p');
    empty.className = 'upcoming-subtitle';
    empty.textContent = 'No upcoming events in the current lookahead window.';
    list.appendChild(empty);
    return;
  }

  for (const item of upcoming) {
    const fragment = template.content.cloneNode(true);
    fragment.querySelector('.upcoming-range').textContent = item.range;
    fragment.querySelector('.upcoming-title').textContent = item.title;
    fragment.querySelector('.upcoming-subtitle').textContent = item.subtitle;
    list.appendChild(fragment);
  }
}

function renderProviders(providers) {
  const host = byId('providerStatus');
  host.innerHTML = '';
  for (const provider of providers) {
    const link = document.createElement(provider.configured ? 'a' : 'span');
    link.className = `provider-pill ${provider.connected ? 'is-connected' : ''}`.trim();
    link.textContent = provider.displayName;
    if (provider.configured) {
      link.href = provider.connectUrl;
    }
    host.appendChild(link);
  }
}

function applyPayload(payload) {
  state.payload = payload;
  byId('clock').textContent = payload.clock;
  byId('dateLabel').textContent = payload.dateLabel;
  byId('heading').textContent = payload.heading;
  byId('subheading').textContent = payload.subheading;
  byId('currentTitle').textContent = payload.currentTitle;
  byId('currentSubtitle').textContent = payload.currentSubtitle;
  byId('remainingMinutes').textContent = String(payload.remainingMinutes);
  byId('ringLabel').textContent = payload.ringLabel;
  updateRing(payload.progress);

  const nextEvent = byId('nextEvent');
  if (payload.nextEvent) {
    nextEvent.textContent = formatRangeForNext(payload.nextEvent);
    nextEvent.classList.remove('hidden');
  } else {
    nextEvent.textContent = '';
    nextEvent.classList.add('hidden');
  }

  renderUpcoming(payload.upcoming || []);
  renderProviders(payload.providers || []);
  byId('errorBar').textContent = (payload.errors || []).join(' | ');
}

function updateCountdown() {
  if (!state.payload || !state.payload.currentEvent) {
    return;
  }

  const now = new Date();
  const end = new Date(state.payload.currentEvent.endsAt);
  const start = new Date(state.payload.currentEvent.startsAt);
  const totalSeconds = Math.max((end - start) / 1000, 1);
  const remainingSeconds = Math.max((end - now) / 1000, 0);
  byId('remainingMinutes').textContent = String(Math.ceil(remainingSeconds / 60));
  updateRing(remainingSeconds / totalSeconds);
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

window.addEventListener('DOMContentLoaded', () => {
  if (window.APP_BOOTSTRAP.connectedProvider) {
    byId('errorBar').textContent = `${window.APP_BOOTSTRAP.connectedProvider} connected.`;
  }
  refreshLoop();
  window.setInterval(refreshLoop, 30000);
  state.countdownInterval = window.setInterval(updateCountdown, 1000);
});
