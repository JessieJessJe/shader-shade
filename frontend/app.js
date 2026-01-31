const fileInput = document.getElementById("fileInput");
const uploadBtn = document.getElementById("uploadBtn");
const runBtn = document.getElementById("runBtn");
const uploadStatus = document.getElementById("uploadStatus");
const runStatus = document.getElementById("runStatus");
const iterationsEl = document.getElementById("iterations");
const bestEl = document.getElementById("best");
const originalImage = document.getElementById("originalImage");

const fftWeight = document.getElementById("fftWeight");
const edgeWeight = document.getElementById("edgeWeight");
const gramWeight = document.getElementById("gramWeight");
const fftVal = document.getElementById("fftVal");
const edgeVal = document.getElementById("edgeVal");
const gramVal = document.getElementById("gramVal");

let imageId = null;
originalImage.src = "/assets/uploads/test1.png";
uploadStatus.textContent = "Using default image: /assets/uploads/test1.png";

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

  originalImage.src = URL.createObjectURL(file);
  uploadStatus.textContent = "Uploaded to memory. Ready to run.";
});

runBtn.addEventListener("click", async () => {
  iterationsEl.innerHTML = "";
  bestEl.innerHTML = "";
  runStatus.textContent = "Starting run...";
  runStatus.classList.add("running");

  const payload = {
    image_id: imageId,
    iterations: 5,
    weights: {
      fft: Number(fftWeight.value),
      edge: Number(edgeWeight.value),
      gram: Number(gramWeight.value),
    },
  };

  let data = null;
  try {
    runStatus.textContent = `Running ${payload.iterations} iterations...`;
    const res = await fetch("/api/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    data = await res.json();
  } catch (err) {
    runStatus.textContent = `Run failed: ${err}`;
    runStatus.classList.remove("running");
    return;
  }

  if (data.input_image) {
    originalImage.src = data.input_image;
  }

  data.iterations.forEach((iter) => {
    const card = document.createElement("div");
    card.className = "iter-card";
    card.innerHTML = `
      <div>Iteration ${iter.iteration}</div>
      <div>Score: ${iter.score.toFixed(3)}</div>
      ${iter.compile_error ? `<div class="muted">Compile error: ${iter.compile_error}</div>` : ""}
      <img src="${iter.render_path}" alt="iteration ${iter.iteration}" />
      <details>
        <summary>GLSL</summary>
        <pre>${iter.shader_code}</pre>
      </details>
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

  runStatus.textContent = "Run complete.";
  runStatus.classList.remove("running");
});
