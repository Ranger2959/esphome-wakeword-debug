type Clip = {
  id: number;
  filename: string;
  timestamp: string;
  duration_seconds: number | null;
  assistant_id: string | null;
  sample_rate: number | null;
  label: string | null;
  deleted: boolean;
  audio_url: string;
};

type ClipResponse = {
  clips: Clip[];
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
  unlabeled_total: number;
};

const listEl = document.getElementById("list") as HTMLDivElement;
const emptyEl = document.getElementById("empty") as HTMLDivElement;
const countEl = document.getElementById("clip-count") as HTMLSpanElement;
const unlabeledCountEl = document.getElementById("unlabeled-count") as HTMLSpanElement;
const rangeEl = document.getElementById("range-label") as HTMLSpanElement;

const startInput = document.getElementById("start") as HTMLInputElement;
const endInput = document.getElementById("end") as HTMLInputElement;
const labelFilter = document.getElementById("label-filter") as HTMLSelectElement;
const showDeletedCheckbox = document.getElementById("show-deleted") as HTMLInputElement;
const applyBtn = document.getElementById("apply") as HTMLButtonElement;
const clearBtn = document.getElementById("clear") as HTMLButtonElement;
const downloadBtn = document.getElementById("download") as HTMLButtonElement;
const refreshBtn = document.getElementById("refresh") as HTMLButtonElement;
const captureNoiseBtn = document.getElementById("capture-noise") as HTMLButtonElement;

// Pagination elements
const pageSizeSelect = document.getElementById("page-size") as HTMLSelectElement;
const pagerEl = document.getElementById("pager") as HTMLElement;
const pageStatusEl = document.getElementById("page-status") as HTMLSpanElement;
const pageFirstBtn = document.getElementById("page-first") as HTMLButtonElement;
const pagePrevBtn = document.getElementById("page-prev") as HTMLButtonElement;
const pageNextBtn = document.getElementById("page-next") as HTMLButtonElement;
const pageLastBtn = document.getElementById("page-last") as HTMLButtonElement;

let currentPage = 1;
let totalPages = 1;

// Resolve backend routes relative to /ui/ so direct access and HA Ingress both work.
const appUrl = (path: string): string =>
  new URL(`../${path.replace(/^\/+/, "")}`, window.location.href).toString();

// Dialog elements
const noiseDialog = document.getElementById("noise-dialog") as HTMLDivElement;
const dialogClose = document.getElementById("dialog-close") as HTMLButtonElement;
const dialogCancel = document.getElementById("dialog-cancel") as HTMLButtonElement;
const dialogConfirm = document.getElementById("dialog-confirm") as HTMLButtonElement;
const secondsInput = document.getElementById("seconds-input") as HTMLInputElement;
const assistantInput = document.getElementById("assistant-input") as HTMLSelectElement;

const formatDate = (value: string) => {
  const date = new Date(value);
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "medium",
  }).format(date);
};

const formatDuration = (value: number | null) => {
  if (value === null || Number.isNaN(value)) return "Unknown";
  return `${value.toFixed(2)}s`;
};

const setRangeLabel = () => {
  if (!startInput.value && !endInput.value) {
    rangeEl.textContent = "All time";
    return;
  }
  const start = startInput.value ? new Date(startInput.value) : null;
  const end = endInput.value ? new Date(endInput.value) : null;
  if (start && end) {
    rangeEl.textContent = `${start.toLocaleString()} → ${end.toLocaleString()}`;
  } else if (start) {
    rangeEl.textContent = `From ${start.toLocaleString()}`;
  } else if (end) {
    rangeEl.textContent = `Until ${end.toLocaleString()}`;
  }
};

const isUnlabeled = (clip: Clip): boolean => {
  return !clip.label || clip.label === "Unknown";
};

const buildQuery = () => {
  const params = new URLSearchParams();
  if (startInput.value) {
    params.set("start", new Date(startInput.value).toISOString());
  }
  if (endInput.value) {
    params.set("end", new Date(endInput.value).toISOString());
  }
  if (labelFilter.value !== "all") {
    params.set("label", labelFilter.value);
  }
  if (showDeletedCheckbox.checked) {
    params.set("include_deleted", "true");
  }
  const query = params.toString();
  return query ? `?${query}` : "";
};

const renderPager = () => {
  pageStatusEl.textContent = `Page ${currentPage} of ${totalPages}`;
  const atFirst = currentPage <= 1;
  const atLast = currentPage >= totalPages;
  pageFirstBtn.disabled = atFirst;
  pagePrevBtn.disabled = atFirst;
  pageNextBtn.disabled = atLast;
  pageLastBtn.disabled = atLast;
  pagerEl.classList.toggle("hidden", totalPages <= 1);
};

const render = (data: ClipResponse) => {
  const clips = data.clips;
  listEl.innerHTML = "";
  countEl.textContent = data.total.toString();
  unlabeledCountEl.textContent = data.unlabeled_total.toString();

  currentPage = data.page;
  totalPages = data.total_pages;
  renderPager();

  if (clips.length === 0) {
    emptyEl.classList.remove("hidden");
    return;
  }
  emptyEl.classList.add("hidden");

  for (const clip of clips) {
    const card = document.createElement("div");
    card.className = "clip-card";
    if (clip.deleted) {
      card.classList.add("deleted");
    }

    // Add visual indicator for unlabeled clips
    if (isUnlabeled(clip)) {
      card.classList.add("unlabeled");
    }

    const header = document.createElement("div");
    header.className = "clip-header";

    const title = document.createElement("div");
    title.className = "clip-title";
    title.textContent = clip.filename;

    const badges = document.createElement("div");
    badges.className = "badges";

    const assistantBadge = document.createElement("span");
    assistantBadge.className = "badge";
    assistantBadge.textContent = clip.assistant_id ?? "assistant";
    badges.appendChild(assistantBadge);

    const labelBadge = document.createElement("span");
    labelBadge.className = "badge label-badge";
    const labelText = clip.label ?? "Unknown";
    const wasUnlabeled = isUnlabeled(clip);

    // Add a visual indicator for labeled vs unlabeled
    if (!wasUnlabeled) {
      labelBadge.textContent = `✓ ${labelText}`;
    } else {
      labelBadge.textContent = `⚠ ${labelText}`;
      labelBadge.classList.add("unlabeled");
    }
    labelBadge.setAttribute("data-label", labelText);
    badges.appendChild(labelBadge);

    if (clip.deleted) {
      const deletedBadge = document.createElement("span");
      deletedBadge.className = "badge deleted-badge";
      deletedBadge.textContent = "Deleted";
      badges.appendChild(deletedBadge);
    }

    header.appendChild(title);
    header.appendChild(badges);

    const meta = document.createElement("div");
    meta.className = "clip-meta";
    meta.innerHTML = `
      <div>Captured: ${formatDate(clip.timestamp)}</div>
      <div>Duration: ${formatDuration(clip.duration_seconds)}</div>
      <div>Sample Rate: ${clip.sample_rate ?? "Unknown"} Hz</div>
    `;

    const audio = document.createElement("audio");
    audio.controls = true;
    // Duration comes from the database, so defer the WAV fetch until playback.
    audio.preload = "none";
    audio.src = appUrl(clip.audio_url);

    const actions = document.createElement("div");
    actions.className = "actions";

    const positiveBtn = document.createElement("button");
    positiveBtn.className = "positive";
    positiveBtn.textContent = "✓ True Positive";

    const falsePositiveBtn = document.createElement("button");
    falsePositiveBtn.className = "false-positive";
    falsePositiveBtn.textContent = "✗ False Positive";

    const falseNegativeBtn = document.createElement("button");
    falseNegativeBtn.className = "false-negative";
    falseNegativeBtn.textContent = "⊘ False Negative";

    const backgroundNoiseBtn = document.createElement("button");
    backgroundNoiseBtn.className = "background-noise";
    backgroundNoiseBtn.textContent = "♪ Background Noise";

    const deleteBtn = document.createElement("button");
    deleteBtn.className = "delete";
    deleteBtn.textContent = clip.deleted ? "↺ Undelete" : "🗑 Delete";

    const lockButtons = (locked: boolean) => {
      positiveBtn.disabled = locked;
      falsePositiveBtn.disabled = locked;
      falseNegativeBtn.disabled = locked;
      backgroundNoiseBtn.disabled = locked;
      deleteBtn.disabled = locked;
    };

    const labelClip = async (
      label: "Positive" | "False Positive" | "False Negative" | "Background Noise",
    ) => {
      lockButtons(true);
      try {
        const response = await fetch(appUrl(`/api/clips/${clip.id}/label`), {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ label }),
        });
        if (!response.ok) {
          throw new Error("Failed to label clip");
        }

        // Update clip label
        const wasUnlabeled = isUnlabeled(clip);
        clip.label = label;

        // Update the label badge with visual indicator
        labelBadge.textContent = `✓ ${label}`;
        labelBadge.setAttribute("data-label", label);
        labelBadge.classList.remove("unlabeled");

        // Update the card styling
        card.classList.remove("unlabeled");

        // Update unlabeled count if it changed from unlabeled to labeled
        if (wasUnlabeled) {
          const currentCount = parseInt(unlabeledCountEl.textContent || "0");
          unlabeledCountEl.textContent = Math.max(0, currentCount - 1).toString();
        }

        lockButtons(false);
      } catch (error) {
        console.error(error);
        lockButtons(false);
      }
    };

    const toggleDelete = async () => {
      lockButtons(true);
      try {
        const endpoint = clip.deleted ? "undelete" : "delete";
        const response = await fetch(appUrl(`/api/clips/${clip.id}/${endpoint}`), {
          method: "POST",
        });
        if (!response.ok) {
          throw new Error(`Failed to ${endpoint} clip`);
        }
        // Reload the list to reflect changes
        load();
      } catch (error) {
        console.error(error);
        lockButtons(false);
      }
    };

    positiveBtn.addEventListener("click", () => labelClip("Positive"));
    falsePositiveBtn.addEventListener("click", () => labelClip("False Positive"));
    falseNegativeBtn.addEventListener("click", () => labelClip("False Negative"));
    backgroundNoiseBtn.addEventListener("click", () => labelClip("Background Noise"));
    deleteBtn.addEventListener("click", toggleDelete);

    actions.appendChild(positiveBtn);
    actions.appendChild(falsePositiveBtn);
    actions.appendChild(falseNegativeBtn);
    actions.appendChild(backgroundNoiseBtn);
    actions.appendChild(deleteBtn);

    card.appendChild(header);
    card.appendChild(meta);
    card.appendChild(audio);
    card.appendChild(actions);

    listEl.appendChild(card);
  }
};

const emptyResponse = (): ClipResponse => ({
  clips: [],
  page: 1,
  page_size: parseInt(pageSizeSelect.value, 10),
  total: 0,
  total_pages: 1,
  unlabeled_total: 0,
});

const load = async () => {
  setRangeLabel();
  const params = new URLSearchParams(buildQuery().replace(/^\?/, ""));
  params.set("page", currentPage.toString());
  params.set("page_size", pageSizeSelect.value);
  const response = await fetch(appUrl(`/api/clips?${params.toString()}`));
  if (!response.ok) {
    render(emptyResponse());
    return;
  }
  const data = (await response.json()) as ClipResponse;
  render(data);
};

// Filter changes invalidate the current offset, so restart from page one.
const loadFirstPage = () => {
  currentPage = 1;
  load();
};

const goToPage = (page: number) => {
  const target = Math.min(Math.max(1, page), totalPages);
  if (target === currentPage) return;
  currentPage = target;
  load();
  window.scrollTo({ top: 0, behavior: "smooth" });
};

pageFirstBtn.addEventListener("click", () => goToPage(1));
pagePrevBtn.addEventListener("click", () => goToPage(currentPage - 1));
pageNextBtn.addEventListener("click", () => goToPage(currentPage + 1));
pageLastBtn.addEventListener("click", () => goToPage(totalPages));
pageSizeSelect.addEventListener("change", loadFirstPage);

applyBtn.addEventListener("click", () => {
  loadFirstPage();
});

clearBtn.addEventListener("click", () => {
  startInput.value = "";
  endInput.value = "";
  loadFirstPage();
});

downloadBtn.addEventListener("click", () => {
  const query = buildQuery();
  window.location.href = appUrl(`/api/clips/download${query}`);
});

refreshBtn.addEventListener("click", () => {
  load();
});

// Dialog handlers
const openNoiseDialog = async () => {
  // Fetch active assistants and populate dropdown
  try {
    const response = await fetch(appUrl("/api/assistants"));
    if (response.ok) {
      const data = await response.json();
      const assistants = data.assistants || ["default"];

      // Clear and populate assistant dropdown
      assistantInput.innerHTML = "";
      for (const assistant of assistants) {
        const option = document.createElement("option");
        option.value = assistant;
        option.textContent = assistant;
        assistantInput.appendChild(option);
      }
    }
  } catch (error) {
    console.error("Failed to fetch assistants:", error);
    // Fallback to default if fetch fails
    assistantInput.innerHTML = "";
    const option = document.createElement("option");
    option.value = "default";
    option.textContent = "default";
    assistantInput.appendChild(option);
  }

  noiseDialog.classList.remove("hidden");
};

const closeNoiseDialog = () => {
  noiseDialog.classList.add("hidden");
};

const captureBackgroundNoise = async () => {
  const seconds = parseFloat(secondsInput.value);
  const assistantId = assistantInput.value;

  if (isNaN(seconds) || seconds <= 0) {
    alert("Please enter a valid number of seconds");
    return;
  }

  // Disable confirm button during request
  dialogConfirm.disabled = true;

  try {
    const response = await fetch(appUrl("/api/capture_background_noise"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ seconds, assistant_id: assistantId }),
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || "Failed to capture background noise");
    }

    const result = await response.json();

    // Close dialog and reload clips
    closeNoiseDialog();
    load();

    // Show success message (optional)
    console.log("Background noise captured:", result);
  } catch (error) {
    console.error("Error capturing background noise:", error);
    alert(error instanceof Error ? error.message : "Failed to capture background noise");
  } finally {
    dialogConfirm.disabled = false;
  }
};

captureNoiseBtn.addEventListener("click", openNoiseDialog);
dialogClose.addEventListener("click", closeNoiseDialog);
dialogCancel.addEventListener("click", closeNoiseDialog);
dialogConfirm.addEventListener("click", captureBackgroundNoise);

// Close dialog when clicking outside
noiseDialog.addEventListener("click", (e) => {
  if (e.target === noiseDialog) {
    closeNoiseDialog();
  }
});

load();
