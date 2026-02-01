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
const agentNotesEl = document.getElementById("agentNotes");
const numFramesInput = document.getElementById("numFramesInput");
const referenceShaderInput = document.getElementById("referenceShaderInput");
const progressBar = document.getElementById("progressBar");
const modal = document.getElementById("modal");
const modalTitle = document.getElementById("modalTitle");
const modalBody = document.getElementById("modalBody");
const modalClose = document.getElementById("modalClose");

let imageId = null;
let activeIntervals = [];
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

const openModal = (title, body) => {
  if (!modal || !modalTitle || !modalBody) return;
  modalTitle.textContent = title;
  modalBody.textContent = body;
  modal.classList.remove("hidden");
};

const closeModal = () => {
  if (!modal) return;
  modal.classList.add("hidden");
};

if (modalClose) {
  modalClose.addEventListener("click", closeModal);
}
if (modal) {
  modal.addEventListener("click", (event) => {
    if (event.target === modal) closeModal();
  });
}

document.addEventListener("click", (event) => {
  const button = event.target.closest(".modal-trigger");
  if (!button) return;
  const title = button.getAttribute("data-title") || "";
  const bodyId = button.getAttribute("data-body");
  const bodyEl = bodyId ? document.getElementById(bodyId) : null;
  openModal(title, bodyEl ? bodyEl.textContent : "");
});


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

const addIterationCard = (iter) => {
  const lpips = iter.lpips_score;
  const card = document.createElement("div");
  card.className = "iter-card";
  const compileStatus = iter.compile_error ? "compile error" : "compiled";
  const notesId = `notes-${iter.iteration}`;
  const critiqueId = `critique-${iter.iteration}`;
  const glslId = `glsl-${iter.iteration}`;

  const framePaths = iter.render_paths || [iter.render_path];
  let lpipsDisplay = lpips == null ? "n/a" : lpips.toFixed(4);
  if (framePaths.length > 1) {
    lpipsDisplay += ` (best of ${framePaths.length})`;
  }

  card.innerHTML = `
    <div>Iteration ${iter.iteration}</div>
    <div class="muted">LPIPS: ${lpipsDisplay}</div>
    <div class="muted">Status: ${compileStatus}</div>
    ${iter.compile_error ? `<div class="muted">Error: ${iter.compile_error}</div>` : ""}
    <div class="frame-viewer">
      <img class="frame-img" src="${framePaths[0]}" alt="iteration ${iter.iteration}" />
      ${framePaths.length > 1 ? `<div class="frame-counter muted">Frame 1 / ${framePaths.length}</div>` : ""}
    </div>
    ${iter.agent_notes ? `<button class="modal-trigger" data-title="Agent Notes" data-body="${notesId}">Agent Notes</button>` : ""}
    ${iter.critique ? `<button class="modal-trigger" data-title="Critique" data-body="${critiqueId}">Critique</button>` : ""}
    <button class="modal-trigger" data-title="GLSL" data-body="${glslId}">GLSL</button>
  `;
  const store = document.createElement("div");
  store.className = "hidden";
  store.innerHTML = `
    <pre id="${notesId}">${iter.agent_notes || ""}</pre>
    <pre id="${critiqueId}">${iter.critique || ""}</pre>
    <pre id="${glslId}">${iter.shader_code || ""}</pre>
  `;
  card.appendChild(store);
  iterationsEl.appendChild(card);

  if (framePaths.length > 1) {
    const imgEl = card.querySelector(".frame-img");
    const counterEl = card.querySelector(".frame-counter");
    let currentFrame = 0;
    const intervalId = setInterval(() => {
      currentFrame = (currentFrame + 1) % framePaths.length;
      imgEl.src = framePaths[currentFrame];
      if (counterEl) counterEl.textContent = `Frame ${currentFrame + 1} / ${framePaths.length}`;
    }, 250);
    activeIntervals.push(intervalId);
  }
};

runBtn.addEventListener("click", async () => {
  activeIntervals.forEach(id => clearInterval(id));
  activeIntervals = [];
  iterationsEl.innerHTML = "";
  bestEl.innerHTML = "";
  discoveryNotesEl.innerHTML = "";
  agentNotesEl.innerHTML = "";
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
  const numFramesValue = Math.max(1, Math.min(30, Number(numFramesInput?.value || 1)));
  const payload = {
    image_id: imageId,
    iterations: iterationsValue,
    num_frames: numFramesValue,
    reference_text: referenceShaderInput?.value || null,
  };

  let res;
  try {
    runStatus.textContent = "Running discovery...";
    res = await fetch("/api/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  } catch (err) {
    runStatus.textContent = `Run failed: ${err}`;
    runStatus.classList.remove("running");
    if (progressBar) {
      progressBar.classList.remove("running");
      progressBar.style.width = "0%";
    }
    return;
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let iterCount = 0;

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    const parts = buffer.split("\n\n");
    buffer = parts.pop();

    for (const part of parts) {
      if (!part.trim()) continue;
      let eventType = "";
      let dataStr = "";
      for (const line of part.split("\n")) {
        if (line.startsWith("event: ")) eventType = line.slice(7);
        else if (line.startsWith("data: ")) dataStr = line.slice(6);
      }
      if (!eventType || !dataStr) continue;

      let data;
      try { data = JSON.parse(dataStr); } catch { continue; }

      if (eventType === "input_image") {
        if (data.input_image) originalImage.src = data.input_image;
      } else if (eventType === "discovery") {
        runStatus.textContent = `Running iteration 1 of ${iterationsValue}...`;
        if (progressBar) progressBar.style.width = `${Math.round(100 / (iterationsValue + 1))}%`;
        let gapHtml = "";
        if (data.gap_analysis) {
          let gap = data.gap_analysis;
          if (typeof gap === "string") {
            try { gap = JSON.parse(gap); } catch {}
          }
          if (typeof gap === "object" && gap !== null) {
            for (const [key, value] of Object.entries(gap)) {
              gapHtml += `<div class="discovery-section"><div class="discovery-label">${key}</div><div>${value}</div></div>`;
            }
          } else {
            gapHtml = `<div class="discovery-section"><div>${gap}</div></div>`;
          }
        }
        if (data.notes) {
          gapHtml += `<div class="discovery-section"><div class="discovery-label">NOTES</div><div>${data.notes}</div></div>`;
        }
        const block = document.createElement("div");
        block.className = "note-item discovery-card";
        block.innerHTML = gapHtml;
        discoveryNotesEl.appendChild(block);
      } else if (eventType === "iteration") {
        iterCount++;
        runStatus.textContent = iterCount < iterationsValue
          ? `Running iteration ${iterCount + 1} of ${iterationsValue}...`
          : "Finishing up...";
        if (progressBar) progressBar.style.width = `${Math.round(((iterCount + 1) / (iterationsValue + 1)) * 100)}%`;
        addIterationCard(data);
        const noteItem = document.createElement("div");
        noteItem.className = "note-item";
        noteItem.innerHTML = `
          <div class="note-title">Iteration ${data.iteration}</div>
          <pre>${data.agent_notes || "No notes."}</pre>
        `;
        agentNotesEl.appendChild(noteItem);
      } else if (eventType === "best") {
        if (data.render_path) {
          bestEl.innerHTML = `
            <div>Best ${data.metric || "lpips"}: ${data.score != null ? data.score.toFixed(4) : "n/a"}</div>
            <img src="${data.render_path}" alt="best output" />
            <button class="modal-trigger" data-title="Best GLSL" data-body="best-glsl">GLSL</button>
            <div class="hidden"><pre id="best-glsl">${data.shader_code}</pre></div>
          `;
        }
      } else if (eventType === "done") {
        runStatus.textContent = "Run complete.";
        runStatus.classList.remove("running");
        if (progressBar) {
          progressBar.classList.remove("running");
          progressBar.style.width = "100%";
        }
      }
    }
  }

  // Ensure we mark complete even if done event was missed
  runStatus.textContent = "Run complete.";
  runStatus.classList.remove("running");
  if (progressBar) {
    progressBar.classList.remove("running");
    progressBar.style.width = "100%";
  }
});
