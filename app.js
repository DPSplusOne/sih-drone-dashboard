const toast = document.getElementById('toast');
const toastTitle = document.getElementById('toast-title');
const toastCopy = document.getElementById('toast-copy');
let toastTimer;

function showToast(title, copy) {
  toastTitle.textContent = title;
  toastCopy.textContent = copy;
  toast.classList.add('show');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => toast.classList.remove('show'), 3400);
}

document.getElementById('new-mission').addEventListener('click', () => {
  showToast('Mission draft created', 'Configure its route in Mission Simulator.');
});

document.getElementById('deploy-model').addEventListener('click', (event) => {
  event.currentTarget.textContent = 'Model queued for deployment ✓';
  event.currentTarget.classList.add('deployed');
  showToast('Deployment queued', 'Classifier v2.8 will be available to C2 shortly.');
});

document.getElementById('center-map').addEventListener('click', () => {
  showToast('Operation centered', 'Alpha Range · Sector 04 is in focus.');
});

document.querySelectorAll('.drone-pin').forEach((pin) => {
  pin.addEventListener('click', () => {
    const drone = pin.dataset.drone;
    document.getElementById('selected-drone').textContent = drone;
    document.getElementById('flight-label').textContent = `${drone} · Surveyor`;
    showToast(`${drone} selected`, 'Live telemetry stream connected.');
  });
});

document.querySelectorAll('.segmented-control button').forEach((button) => {
  button.addEventListener('click', () => {
    document.querySelectorAll('.segmented-control button').forEach((item) => item.classList.remove('selected'));
    button.classList.add('selected');
    showToast(`${button.textContent} layer enabled`, 'Airspace visualisation updated.');
  });
});

document.querySelectorAll('.nav a').forEach((link) => {
  link.addEventListener('click', () => {
    document.querySelectorAll('.nav a').forEach((item) => item.classList.remove('active'));
    link.classList.add('active');
  });
});
