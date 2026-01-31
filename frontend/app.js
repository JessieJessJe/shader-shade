const fileInput = document.getElementById("fileInput");
const uploadBtn = document.getElementById("uploadBtn");
const runBtn = document.getElementById("runBtn");
const uploadStatus = document.getElementById("uploadStatus");
const iterationsEl = document.getElementById("iterations");
const bestEl = document.getElementById("best");

const fftWeight = document.getElementById("fftWeight");
const edgeWeight = document.getElementById("edgeWeight");
const gramWeight = document.getElementById("gramWeight");
const fftVal = document.getElementById("fftVal");
const edgeVal = document.getElementById("edgeVal");
const gramVal = document.getElementById("gramVal");

let imageId = null;

function updateLabels() {
  fftVal.textContent = Number(fftWeight.value).toFixed(2);
  edgeVal.textContent = Number(edgeWeight.value).toFixed(2);
  gramVal.textContent = Number(gramWeight.value).toFixed(2);
}

[fftWeight, edgeWeight, gramWeight].forEach((el) => {
  el.addEventListener("input", updateLabels);
});

updateLabels();

uploadBtn.addEventListener("click", async () => {
  const file = fileInput.files[0];
  if (!file) return;

  uploadStatus.textContent = "Uploading...";
  const form = new FormData();
  form.append("file", file);

  const res = await fetch("/api/upload", { method: "POST", body: form });
  const data = await res.json();
  imageId = data.image_id;

  uploadStatus.textContent = `Uploaded: ${data.path}`;
  runBtn.disabled = false;
});

runBtn.addEventListener("click", async () => {
  if (!imageId) return;

  iterationsEl.innerHTML = "";
  bestEl.innerHTML = "";
  runBtn.disabled = true;

  const payload = {
    image_id: imageId,
    iterations: 4,
    weights: {
      fft: Number(fftWeight.value),
      edge: Number(edgeWeight.value),
      gram: Number(gramWeight.value),
    },
  };

  const res = await fetch("/api/run", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const data = await res.json();

  data.iterations.forEach((iter) => {
    const params = iter.params || {};
    const card = document.createElement("div");
    card.className = "iter-card";
    card.innerHTML = `
      <div>Iteration ${iter.iteration}</div>
      <div>Score: ${iter.score.toFixed(3)}</div>
      <div class="muted">freq ${Number(params.frequency || 0).toFixed(2)} · blend ${Number(params.blend || 0).toFixed(2)}</div>
      <img src="${iter.render_path}" alt="iteration ${iter.iteration}" />
    `;
    iterationsEl.appendChild(card);
  });

  if (data.best?.render_path) {
    bestEl.innerHTML = `
      <div>Best score: ${data.best.score.toFixed(3)}</div>
      <img src="${data.best.render_path}" alt="best output" />
      <pre>${data.best.shader_code}</pre>
    `;
  }

  runBtn.disabled = false;
});
