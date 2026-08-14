const fields = {
  problemata_id: document.getElementById("problemata_id"),
  version: document.getElementById("version"),
  tenant_id: document.getElementById("tenant_id"),
  owner_principal: document.getElementById("owner_principal"),
  description: document.getElementById("description"),
  endpoint_base: document.getElementById("endpoint_base"),
  trust_domain: document.getElementById("trust_domain"),
  include_asyncgate: document.getElementById("include_asyncgate"),
  include_cognigate: document.getElementById("include_cognigate"),
  include_delegategate: document.getElementById("include_delegategate"),
  include_interrogate: document.getElementById("include_interrogate"),
  include_interview: document.getElementById("include_interview"),
  include_memorygate: document.getElementById("include_memorygate"),
  receipt_schema_version: document.getElementById("receipt_schema_version"),
  depot_default_sink: document.getElementById("depot_default_sink"),
  cgn_model: document.getElementById("cgn_model"),
  dlg_model: document.getElementById("dlg_model"),
  interrogate_policy_profile_id: document.getElementById("interrogate_policy_profile_id"),
  async_lease_ttl_seconds: document.getElementById("async_lease_ttl_seconds"),
  async_max_attempts: document.getElementById("async_max_attempts"),
  async_retry_backoff_seconds: document.getElementById("async_retry_backoff_seconds"),
};

const previewButton = document.getElementById("preview-btn");
const createBlueprintButton = document.getElementById("create-blueprint-btn");
const validateButton = document.getElementById("validate-btn");
const registerButton = document.getElementById("register-btn");
const updateButton = document.getElementById("update-btn");
const refreshButton = document.getElementById("refresh-btn");
const specEditor = document.getElementById("spec-json");
const statusLine = document.getElementById("status-line");
const selectedLine = document.getElementById("selected-line");
const validationOutput = document.getElementById("validation-output");
const registryList = document.getElementById("registry-list");
const topologyGraph = document.getElementById("topology-graph");
const edgeDiagnostics = document.getElementById("edge-diagnostics");

const state = {
  selectedProblemataId: null,
};

function buildBlueprintPayload() {
  return {
    problemata_id: fields.problemata_id.value.trim(),
    version: fields.version.value.trim(),
    tenant_id: fields.tenant_id.value.trim(),
    owner_principal: fields.owner_principal.value.trim(),
    description: fields.description.value.trim() || null,
    endpoint_base: fields.endpoint_base.value.trim(),
    trust_domain: fields.trust_domain.value.trim(),
    include_asyncgate: fields.include_asyncgate.checked,
    include_cognigate: fields.include_cognigate.checked,
    include_delegategate: fields.include_delegategate.checked,
    include_interrogate: fields.include_interrogate.checked,
    include_interview: fields.include_interview.checked,
    include_memorygate: fields.include_memorygate.checked,
    receipt_schema_version: fields.receipt_schema_version.value.trim(),
    depot_default_sink: fields.depot_default_sink.value.trim(),
    cgn_model: fields.cgn_model.value.trim(),
    dlg_model: fields.dlg_model.value.trim(),
    interrogate_policy_profile_id: fields.interrogate_policy_profile_id.value.trim(),
    async_lease_ttl_seconds: Number.parseInt(fields.async_lease_ttl_seconds.value, 10),
    async_max_attempts: Number.parseInt(fields.async_max_attempts.value, 10),
    async_retry_backoff_seconds: Number.parseInt(fields.async_retry_backoff_seconds.value, 10),
  };
}

function readSpecEditor() {
  const raw = specEditor.value.trim();
  if (!raw) {
    throw new Error("Spec JSON is empty.");
  }
  return JSON.parse(raw);
}

function writeSpecEditor(spec) {
  specEditor.value = JSON.stringify(spec, null, 2);
}

function setSelectedProblemata(problemataId) {
  state.selectedProblemataId = problemataId || null;
  if (state.selectedProblemataId) {
    selectedLine.textContent = `Editing: ${state.selectedProblemataId}`;
    updateButton.disabled = false;
  } else {
    selectedLine.textContent = "Editing: none";
    updateButton.disabled = true;
  }
}

function setStatus(message, tone = "default") {
  statusLine.textContent = message;
  statusLine.dataset.tone = tone;
}

function renderValidation(result) {
  validationOutput.textContent = JSON.stringify(result, null, 2);
}

function renderRegistry(records) {
  registryList.innerHTML = "";
  if (!Array.isArray(records) || records.length === 0) {
    registryList.innerHTML = "<li>No registered Problemata yet.</li>";
    return;
  }

  for (const record of records) {
    const item = document.createElement("li");
    const errors = Array.isArray(record.validation?.errors) ? record.validation.errors.length : 0;
    item.innerHTML =
      `<strong>${record.problemata_id}</strong> v${record.version}<br>` +
      `<span class="status ${record.status}">${record.status}</span> | source=${record.source} | errors=${errors}<br>` +
      `<span>${record.created_at}</span><br>` +
      `<button class="load-btn" data-problemata-id="${record.problemata_id}" type="button">Load</button>`;
    registryList.appendChild(item);
  }
}

function renderDiagnosticsList(diagnostics) {
  edgeDiagnostics.innerHTML = "";
  const globalMessages = diagnostics.global_messages || [];
  const edges = diagnostics.edges || [];
  if (edges.length === 0 && globalMessages.length === 0) {
    edgeDiagnostics.innerHTML = "<li>No topology diagnostics yet.</li>";
    return;
  }

  for (const message of globalMessages) {
    const li = document.createElement("li");
    li.className = "diag-item error";
    li.textContent = `Global: ${message}`;
    edgeDiagnostics.appendChild(li);
  }

  for (const edge of edges) {
    if (!Array.isArray(edge.messages) || edge.messages.length === 0) {
      continue;
    }
    const li = document.createElement("li");
    li.className = `diag-item ${edge.status || "ok"}`;
    const summary = `${edge.from_id || "?"} -> ${edge.to_id || "?"} (${edge.purpose || "unknown"})`;
    li.textContent = `${summary}: ${edge.messages.join(" | ")}`;
    edgeDiagnostics.appendChild(li);
  }

  if (!edgeDiagnostics.children.length) {
    edgeDiagnostics.innerHTML = "<li>No edge-level issues. Topology is clean.</li>";
  }
}

function renderTopologyGraph(spec, diagnostics) {
  const primitives = spec.primitives || {};
  const nodes = Array.isArray(diagnostics.nodes) ? diagnostics.nodes : [];
  const edges = Array.isArray(diagnostics.edges) ? diagnostics.edges : [];
  if (!nodes.length) {
    topologyGraph.innerHTML = "";
    return;
  }

  const width = 900;
  const height = 520;
  const centerX = width / 2;
  const centerY = height / 2;
  const radius = Math.min(width, height) * 0.34;
  const positions = {};

  nodes.forEach((node, index) => {
    const angle = (Math.PI * 2 * index) / nodes.length - Math.PI / 2;
    positions[node.primitive_id] = {
      x: centerX + Math.cos(angle) * radius,
      y: centerY + Math.sin(angle) * radius,
    };
  });

  let svg = `
    <defs>
      <marker id="arrow-ok" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto">
        <path d="M0,0 L8,4 L0,8 Z" fill="#1a8a8f"></path>
      </marker>
      <marker id="arrow-warning" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto">
        <path d="M0,0 L8,4 L0,8 Z" fill="#da6f34"></path>
      </marker>
      <marker id="arrow-error" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto">
        <path d="M0,0 L8,4 L0,8 Z" fill="#a22626"></path>
      </marker>
    </defs>
  `;

  edges.forEach((edge) => {
    const from = positions[edge.from_id];
    const to = positions[edge.to_id];
    if (!from || !to) {
      return;
    }
    const status = edge.status || "ok";
    const marker = status === "error" ? "arrow-error" : status === "warning" ? "arrow-warning" : "arrow-ok";
    const labelX = (from.x + to.x) / 2;
    const labelY = (from.y + to.y) / 2 - 6;
    svg += `
      <line class="graph-edge ${status}" x1="${from.x}" y1="${from.y}" x2="${to.x}" y2="${to.y}" marker-end="url(#${marker})"></line>
      <text class="graph-edge-label" x="${labelX}" y="${labelY}">${edge.purpose || "edge"}</text>
    `;
  });

  nodes.forEach((node) => {
    const pos = positions[node.primitive_id];
    const primitive = primitives[node.primitive_id] || {};
    const primitiveType = primitive.type || node.primitive_type || "unknown";
    svg += `
      <circle class="graph-node" cx="${pos.x}" cy="${pos.y}" r="34"></circle>
      <text class="graph-node-id" x="${pos.x}" y="${pos.y - 5}">${node.primitive_id}</text>
      <text class="graph-node-type" x="${pos.x}" y="${pos.y + 13}">${primitiveType}</text>
    `;
  });

  topologyGraph.innerHTML = svg;
}

async function requestJson(url, options = {}) {
  const response = await fetch(url, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail || body);
    throw new Error(detail || `HTTP ${response.status}`);
  }
  return body;
}

async function refreshRegistry() {
  const records = await requestJson("/api/problemata");
  renderRegistry(records);
}

async function runDiagnostics(spec) {
  const diagnostics = await requestJson("/api/problemata/diagnostics", {
    method: "POST",
    body: JSON.stringify({ spec }),
  });
  renderValidation(diagnostics.validation);
  renderDiagnosticsList(diagnostics);
  renderTopologyGraph(spec, diagnostics);
  return diagnostics;
}

async function loadProblemata(problemataId) {
  const record = await requestJson(`/api/problemata/${encodeURIComponent(problemataId)}`);
  writeSpecEditor(record.spec);
  setSelectedProblemata(record.problemata_id);
  await runDiagnostics(record.spec);
  return record;
}

previewButton.addEventListener("click", async () => {
  try {
    setStatus("Compiling blueprint preview...");
    const payload = buildBlueprintPayload();
    const spec = await requestJson("/api/problemata/preview", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    writeSpecEditor(spec);
    setSelectedProblemata(null);
    await runDiagnostics(spec);
    setStatus("Preview generated.", "ok");
  } catch (error) {
    setStatus(`Preview failed: ${error.message}`, "error");
  }
});

createBlueprintButton.addEventListener("click", async () => {
  try {
    setStatus("Creating Problemata from blueprint...");
    const payload = buildBlueprintPayload();
    const record = await requestJson("/api/problemata/from-blueprint", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    writeSpecEditor(record.spec);
    setSelectedProblemata(record.problemata_id);
    await runDiagnostics(record.spec);
    setStatus(`Created ${record.problemata_id} (${record.status}).`, "ok");
    await refreshRegistry();
  } catch (error) {
    setStatus(`Create failed: ${error.message}`, "error");
  }
});

validateButton.addEventListener("click", async () => {
  try {
    setStatus("Validating spec...");
    const spec = readSpecEditor();
    const diagnostics = await runDiagnostics(spec);
    const tone = diagnostics.validation.status === "passed" ? "ok" : "error";
    setStatus(`Validation ${diagnostics.validation.status}.`, tone);
  } catch (error) {
    setStatus(`Validate failed: ${error.message}`, "error");
  }
});

registerButton.addEventListener("click", async () => {
  try {
    setStatus("Registering raw spec...");
    const spec = readSpecEditor();
    const record = await requestJson("/api/problemata", {
      method: "POST",
      body: JSON.stringify({ source: "ui.raw", spec }),
    });
    writeSpecEditor(record.spec);
    setSelectedProblemata(record.problemata_id);
    await runDiagnostics(record.spec);
    const tone = record.status === "validated" ? "ok" : "error";
    setStatus(`Registered ${record.problemata_id} (${record.status}).`, tone);
    await refreshRegistry();
  } catch (error) {
    setStatus(`Register failed: ${error.message}`, "error");
  }
});

updateButton.addEventListener("click", async () => {
  try {
    const spec = readSpecEditor();
    const selectedId = state.selectedProblemataId || spec?.problemata?.id;
    if (!selectedId) {
      throw new Error("No selected Problemata id. Load a record first.");
    }

    setStatus(`Updating ${selectedId}...`);
    const record = await requestJson(`/api/problemata/${encodeURIComponent(selectedId)}`, {
      method: "PUT",
      body: JSON.stringify({ source: "ui.update", spec }),
    });
    writeSpecEditor(record.spec);
    setSelectedProblemata(record.problemata_id);
    await runDiagnostics(record.spec);
    const tone = record.status === "validated" ? "ok" : "error";
    setStatus(`Updated ${record.problemata_id} (${record.status}).`, tone);
    await refreshRegistry();
  } catch (error) {
    setStatus(`Update failed: ${error.message}`, "error");
  }
});

registryList.addEventListener("click", async (event) => {
  const target = event.target;
  if (!(target instanceof HTMLButtonElement)) {
    return;
  }
  if (!target.classList.contains("load-btn")) {
    return;
  }

  const problemataId = target.dataset.problemataId;
  if (!problemataId) {
    return;
  }
  try {
    setStatus(`Loading ${problemataId}...`);
    await loadProblemata(problemataId);
    setStatus(`Loaded ${problemataId}.`, "ok");
  } catch (error) {
    setStatus(`Load failed: ${error.message}`, "error");
  }
});

refreshButton.addEventListener("click", async () => {
  try {
    setStatus("Refreshing registry...");
    await refreshRegistry();
    setStatus("Registry refreshed.", "ok");
  } catch (error) {
    setStatus(`Refresh failed: ${error.message}`, "error");
  }
});

setSelectedProblemata(null);
refreshRegistry().catch((error) => {
  setStatus(`Initial registry load failed: ${error.message}`, "error");
});
