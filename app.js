const toast = document.getElementById('toast');
const toastTitle = document.getElementById('toast-title');
const toastCopy = document.getElementById('toast-copy');
let toastTimer;

function showToast(title, copy) {
  toastTitle.textContent = title;
  toastCopy.textContent = copy;
  toast.classList.add('show');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => toast.classList.remove('show'), 3600);
}

document.getElementById('video-file').addEventListener('change', (event) => {
  const [file] = event.target.files;
  if (!file) return;
  document.getElementById('upload-title').textContent = 'Drone video attached';
  document.getElementById('upload-copy').textContent = `${file.name} · ${(file.size / 1024 / 1024).toFixed(1)} MB`;
  document.getElementById('video-summary').innerHTML = 'Pending <small>scan</small>';
  showToast('Input replaced', 'Run reconstruction to extract frame and camera-quality metrics.');
});

document.getElementById('metadata-toggle').addEventListener('click', (event) => {
  const details = document.querySelector('.input-details');
  const isOpen = details.classList.toggle('show-optional');
  event.currentTarget.textContent = isOpen ? 'Hide details' : 'Show details';
  event.currentTarget.setAttribute('aria-expanded', String(isOpen));
});

document.querySelectorAll('.view-controls button').forEach((button) => {
  button.addEventListener('click', () => {
    document.querySelectorAll('.view-controls button').forEach((item) => item.classList.remove('selected'));
    button.classList.add('selected');
    const isPoints = button.dataset.view === 'points';
    document.getElementById('viewer-canvas').classList.toggle('points-mode', isPoints);
    document.getElementById('view-label').textContent = isPoints ? 'Dense point cloud' : 'Textured mesh';
    showToast(isPoints ? 'Point-cloud inspection enabled' : 'Textured mesh enabled', isPoints ? 'View correspondence density before exporting a surface.' : 'Showing the refined, textured reconstruction.');
  });
});

document.getElementById('focus-model').addEventListener('click', () => {
  document.getElementById('viewer-canvas').classList.toggle('focused');
  showToast('Model focused', 'Preview centered on the highest-confidence geometry.');
});

document.getElementById('start-reconstruction').addEventListener('click', (event) => {
  const button = event.currentTarget;
  const finalStage = document.getElementById('final-stage');
  if (button.dataset.running === 'true') return;
  button.dataset.running = 'true';
  button.disabled = true;
  button.innerHTML = '<span class="button-spinner"></span> Processing';
  document.getElementById('pipeline-status').textContent = 'Finalizing texture atlas and validation';
  document.getElementById('final-stage-copy').textContent = 'Building atlas and assessing confidence';
  showToast('Reconstruction started', 'The local processing queue is working through the final validation stage.');
  setTimeout(() => {
    finalStage.classList.remove('active');
    finalStage.classList.add('complete');
    finalStage.querySelector('i').className = '';
    finalStage.querySelector('i').textContent = '✓';
    document.getElementById('pipeline-status').textContent = '5 of 5 stages completed';
    document.getElementById('pipeline-count').textContent = '5/5';
    document.getElementById('final-stage-copy').textContent = 'Atlas published with validation evidence';
    document.getElementById('frames-summary').textContent = '1,248';
    button.innerHTML = '<span>✓</span> Reconstruction complete';
    showToast('Model published', 'Textured mesh, dense cloud, and validation evidence are ready to export.');
  }, 1700);
});

document.getElementById('export-report').addEventListener('click', () => {
  const report = ['AeroTrace 3D validation summary', 'Project: Heritage Block 07', 'Input: single-pass 4K drone video with GPS, metadata, IMU and PPK corrections', 'Usable frames: 1,248', 'Median reprojection error: 0.24 m', 'Visible-surface coverage: 91.6%', 'Known limit: north facade has low observation and is flagged for review.'].join('\n');
  const link = document.createElement('a');
  link.href = URL.createObjectURL(new Blob([report], { type: 'text/plain' }));
  link.download = 'heritage-block-07-validation.txt';
  link.click();
  URL.revokeObjectURL(link.href);
  showToast('Validation report exported', 'Use the report alongside the model and coverage evidence.');
});

document.getElementById('open-plan').addEventListener('click', () => { window.location.href = 'docs/solution-plan.md'; });
document.querySelectorAll('.nav a').forEach((link) => link.addEventListener('click', () => { document.querySelectorAll('.nav a').forEach((item) => item.classList.remove('active')); link.classList.add('active'); }));
