const fileInput = document.getElementById("fileInput");
const uploadBtn = document.getElementById("uploadBtn");
const runBtn = document.getElementById("runBtn");
const iterationsInput = document.getElementById("iterationsInput");
const uploadStatus = document.getElementById("uploadStatus");
const runStatus = document.getElementById("runStatus");
const iterationsEl = document.getElementById("iterations");
const bestEl = document.getElementById("best");
const originalImage = document.getElementById("originalImage");
const discoveryNotesEl = document.getElementById("discoveryNotes");
const referenceShaderInput = document.getElementById("referenceShaderInput");
const progressBar = document.getElementById("progressBar");

let imageId = null;
originalImage.src = "/assets/uploads/test1.png";
uploadStatus.textContent = "Using default image: /assets/uploads/test1.png";

const referenceStorageKey = "referenceShaderDraft";
if (referenceShaderInput) {
  const savedReference = localStorage.getItem(referenceStorageKey);
  if (savedReference) {
    referenceShaderInput.value = savedReference;
  } else {
    fetch("/static/reference_particle_flow_summary.txt")
      .then((res) => (res.ok ? res.text() : ""))
      .then((text) => {
        if (text) {
          referenceShaderInput.value = text.trim();
        }
      })
      .catch(() => {});
  }
  referenceShaderInput.addEventListener("input", (event) => {
    const value = event.target.value || "";
    localStorage.setItem(referenceStorageKey, value);
  });
}

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
  discoveryNotesEl.innerHTML = "";
  runStatus.textContent = "Starting run...";
  runStatus.classList.add("running");
  if (progressBar) {
    progressBar.style.width = "0%";
    progressBar.classList.add("running");
  }

  const iterationsValue = Math.max(
    1,
    Math.min(8, Number(iterationsInput?.value || 5))
  );
  const payload = {
    image_id: imageId,
    iterations: iterationsValue,
    reference_text: referenceShaderInput?.value || null,
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
    if (progressBar) {
      progressBar.classList.remove("running");
      progressBar.style.width = "0%";
    }
    return;
  }

  if (data.input_image) {
    originalImage.src = data.input_image;
  }

  data.iterations.forEach((iter) => {
    const lpips = iter.lpips_score;
    const card = document.createElement("div");
    card.className = "iter-card";
    const compileStatus = iter.compile_error ? "compile error" : "compiled";
    card.innerHTML = `
      <div>Iteration ${iter.iteration}</div>
      <div class="muted">LPIPS: ${lpips == null ? "n/a" : lpips.toFixed(4)}</div>
      <div class="muted">Status: ${compileStatus}</div>
      ${iter.compile_error ? `<div class="muted">Error: ${iter.compile_error}</div>` : ""}
      <img src="${iter.render_path}" alt="iteration ${iter.iteration}" />
      ${iter.agent_notes ? `<details><summary>Agent Notes</summary><pre>${iter.agent_notes}</pre></details>` : ""}
      ${iter.critique ? `<details><summary>Critique</summary><pre>${iter.critique}</pre></details>` : ""}
      <details>
        <summary>GLSL</summary>
        <pre>${iter.shader_code}</pre>
      </details>
    `;
    iterationsEl.appendChild(card);
  });

  if (data.best?.render_path) {
    bestEl.innerHTML = `
      <div>Best ${data.best.metric || "lpips"}: ${data.best.score.toFixed(4)}</div>
      <img src="${data.best.render_path}" alt="best output" />
      <pre>${data.best.shader_code}</pre>
    `;
  }

  if (data.iterations?.length) {
    const notesList = document.createElement("div");
    notesList.className = "notes-list";
    data.iterations.forEach((iter) => {
      const item = document.createElement("div");
      item.className = "note-item";
      const noteText = iter.agent_notes || "No notes.";
      item.innerHTML = `
        <div class="note-title">Iteration ${iter.iteration}</div>
        <pre>${noteText}</pre>
      `;
      notesList.appendChild(item);
    });
    discoveryNotesEl.appendChild(notesList);
  }

  runStatus.textContent = "Run complete.";
  runStatus.classList.remove("running");
  if (progressBar) {
    progressBar.classList.remove("running");
    progressBar.style.width = "100%";
  }
});
