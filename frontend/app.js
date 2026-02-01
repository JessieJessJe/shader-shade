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
const modal = document.getElementById("modal");
const modalTitle = document.getElementById("modalTitle");
const modalBody = document.getElementById("modalBody");
const modalClose = document.getElementById("modalClose");
const modalSplit = document.getElementById("modalSplit");
const modalCode = document.getElementById("modalCode");
const modalCanvas = document.getElementById("modalCanvas");
const modalError = document.getElementById("modalError");

let imageId = null;
let currentShader = null;
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

let previewState = null;

const stopPreview = () => {
  if (previewState?.rafId) {
    cancelAnimationFrame(previewState.rafId);
  }
  if (previewState?.gl) {
    previewState.gl.getExtension("WEBGL_lose_context")?.loseContext();
  }
  previewState = null;
  if (modalError) modalError.textContent = "";
};

const toWebGLFragment = (shader) => {
  let code = shader.replace(/#version\\s+330\\s*/g, "");
  code = code.replace(/\\bout\\s+vec4\\s+f_color\\s*;/g, "out vec4 outColor;");
  code = code.replace(/\\bf_color\\b/g, "outColor");
  return `#version 300 es\\nprecision highp float;\\n${code}`;
};

const compileShader = (gl, type, source) => {
  const shader = gl.createShader(type);
  gl.shaderSource(shader, source);
  gl.compileShader(shader);
  if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
    const info = gl.getShaderInfoLog(shader);
    gl.deleteShader(shader);
    return { shader: null, error: info || "Shader compile failed." };
  }
  return { shader, error: "" };
};

const buildProgram = (gl, fragmentSource) => {
  const vertexSource = `#version 300 es\nin vec2 in_pos;\nout vec2 v_uv;\nvoid main(){\n  v_uv = in_pos * 0.5 + 0.5;\n  gl_Position = vec4(in_pos, 0.0, 1.0);\n}\n`;
  const vs = compileShader(gl, gl.VERTEX_SHADER, vertexSource);
  if (vs.error) return { program: null, error: vs.error };
  const fs = compileShader(gl, gl.FRAGMENT_SHADER, fragmentSource);
  if (fs.error) return { program: null, error: fs.error };
  const program = gl.createProgram();
  gl.attachShader(program, vs.shader);
  gl.attachShader(program, fs.shader);
  gl.linkProgram(program);
  if (!gl.getProgramParameter(program, gl.LINK_STATUS)) {
    const info = gl.getProgramInfoLog(program);
    gl.deleteProgram(program);
    return { program: null, error: info || "Program link failed." };
  }
  return { program, error: "" };
};

const createTexture = (gl, image) => {
  const tex = gl.createTexture();
  gl.bindTexture(gl.TEXTURE_2D, tex);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
  gl.texImage2D(
    gl.TEXTURE_2D,
    0,
    gl.RGB,
    gl.RGB,
    gl.UNSIGNED_BYTE,
    image
  );
  return tex;
};

const startPreview = (shaderSource) => {
  if (!modalCanvas) return;
  stopPreview();
  const gl = modalCanvas.getContext("webgl2");
  if (!gl) {
    if (modalError) modalError.textContent = "WebGL2 not available.";
    return;
  }
  const fragmentSource = toWebGLFragment(shaderSource);
  const programInfo = buildProgram(gl, fragmentSource);
  if (!programInfo.program) {
    if (modalError) modalError.textContent = programInfo.error;
    return;
  }
  const program = programInfo.program;
  gl.useProgram(program);

  const vertices = new Float32Array([-1, -1, 3, -1, -1, 3]);
  const vbo = gl.createBuffer();
  gl.bindBuffer(gl.ARRAY_BUFFER, vbo);
  gl.bufferData(gl.ARRAY_BUFFER, vertices, gl.STATIC_DRAW);
  const loc = gl.getAttribLocation(program, "in_pos");
  gl.enableVertexAttribArray(loc);
  gl.vertexAttribPointer(loc, 2, gl.FLOAT, false, 0, 0);

  const resolutionLoc = gl.getUniformLocation(program, "u_resolution");
  const timeLoc = gl.getUniformLocation(program, "u_time");
  const inputLoc = gl.getUniformLocation(program, "u_input");

  const image = new Image();
  image.crossOrigin = "anonymous";
  image.src = originalImage?.src || "/assets/uploads/test1.png";
  image.onload = () => {
    const tex = createTexture(gl, image);
    gl.activeTexture(gl.TEXTURE0);
    gl.bindTexture(gl.TEXTURE_2D, tex);
    if (inputLoc) gl.uniform1i(inputLoc, 0);
  };

  const start = performance.now();
  const render = () => {
    const now = performance.now();
    const t = (now - start) / 1000;
    gl.viewport(0, 0, modalCanvas.width, modalCanvas.height);
    if (resolutionLoc) gl.uniform2f(resolutionLoc, modalCanvas.width, modalCanvas.height);
    if (timeLoc) gl.uniform1f(timeLoc, t);
    gl.drawArrays(gl.TRIANGLES, 0, 3);
    previewState.rafId = requestAnimationFrame(render);
  };

  previewState = { gl, program, rafId: null };
  render();
};

const openModal = (title, body) => {
  if (!modal || !modalTitle || !modalBody) return;
  modalTitle.textContent = title;
  if (title.toLowerCase().includes("glsl")) {
    if (modalSplit) modalSplit.classList.remove("hidden");
    if (modalBody) modalBody.classList.add("hidden");
    if (modalCode) modalCode.textContent = body;
    if (modalError) modalError.textContent = "";
    startPreview(body);
  } else {
    if (modalSplit) modalSplit.classList.add("hidden");
    if (modalBody) modalBody.classList.remove("hidden");
    modalBody.textContent = body;
    stopPreview();
  }
  modal.classList.remove("hidden");
};

const closeModal = () => {
  if (!modal) return;
  stopPreview();
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
    currentShader = iter.shader_code;
    const card = document.createElement("div");
    card.className = "iter-card";
    const compileStatus = iter.compile_error ? "compile error" : "compiled";
    const notesId = `notes-${iter.iteration}`;
    const critiqueId = `critique-${iter.iteration}`;
    const glslId = `glsl-${iter.iteration}`;
    card.innerHTML = `
      <div>Iteration ${iter.iteration}</div>
      <div class="muted">LPIPS: ${lpips == null ? "n/a" : lpips.toFixed(4)}</div>
      <div class="muted">Status: ${compileStatus}</div>
      ${iter.compile_error ? `<div class="muted">Error: ${iter.compile_error}</div>` : ""}
      <img src="${iter.render_path}" alt="iteration ${iter.iteration}" />
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
  });

  if (data.best?.render_path) {
    bestEl.innerHTML = `
      <div>Best ${data.best.metric || "lpips"}: ${data.best.score.toFixed(4)}</div>
      <img src="${data.best.render_path}" alt="best output" />
      <button class="modal-trigger" data-title="Best GLSL" data-body="best-glsl">GLSL</button>
      <div class="hidden"><pre id="best-glsl">${data.best.shader_code}</pre></div>
    `;
    currentShader = data.best.shader_code;
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
