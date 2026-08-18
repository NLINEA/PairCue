"use strict";

const byId = (id) => document.getElementById(id);
const form = byId("setup-form");
const preview = byId("config-preview");
const formError = byId("form-error");
const actionStatus = byId("action-status");
const apiToken = randomToken();

const secretIds = new Set([
  "server-token",
  "opensubtitles-key",
  "translation-key",
  "transcription-key",
]);

function selectedPlatform() {
  return form.querySelector('input[name="platform"]:checked').value;
}

function selectedMode() {
  return form.querySelector('input[name="mode"]:checked').value;
}

function value(id) {
  return byId(id).value.trim();
}

function checked(id) {
  return byId(id).checked;
}

function quote(raw) {
  if (/[\u0000-\u001F]/.test(raw)) {
    throw new Error("Configuration values cannot contain control characters.");
  }
  return JSON.stringify(raw);
}

function randomToken() {
  const bytes = new Uint8Array(36);
  crypto.getRandomValues(bytes);
  const binary = Array.from(bytes, (byte) => String.fromCharCode(byte)).join("");
  return btoa(binary).replaceAll("+", "-").replaceAll("/", "_").replaceAll("=", "");
}

function secretValue(id, maskSecrets) {
  const raw = value(id);
  if (!maskSecrets || !raw) {
    return raw;
  }
  return "•••••••• (saved in file)";
}

function configLine(name, raw) {
  return `${name}=${quote(raw)}`;
}

function buildConfig(maskSecrets = false) {
  const mode = selectedMode();
  const platform = selectedPlatform();
  const lines = ["# Generated locally by PairCue Setup. Keep this file private."];
  if (mode === "library") {
    const hostMediaPath = value("host-media-path").replace(/\/+$/, "") || "/";
    const torrentPath = hostMediaPath === "/" ? "/Torrents" : `${hostMediaPath}/Torrents`;
    lines.push(
      configLine("MEDIA_PATH", hostMediaPath),
      configLine("TORRENT_WATCH_PATH", torrentPath),
      configLine("PAIRCUE_PORT", value("host-port")),
      configLine("PUID", value("puid")),
      configLine("PGID", value("pgid")),
      "",
    );
  }
  lines.push(
    configLine("PAIRCUE_PLATFORM", platform),
    configLine("PAIRCUE_MEDIA_ROOT", mode === "library" ? "/media" : "."),
    configLine("PAIRCUE_STATE_DIR", mode === "library" ? "/state" : ".paircue-state"),
    configLine("PAIRCUE_SCAN_INTERVAL_SECONDS", "1800"),
  );

  if (mode === "library" && platform !== "filesystem") {
    lines.push(
      configLine("PAIRCUE_SERVER_URL", value("server-url")),
      configLine("PAIRCUE_SERVER_TOKEN", secretValue("server-token", maskSecrets)),
      configLine("PAIRCUE_SERVER_PATH_PREFIX", value("server-prefix")),
    );
    if (platform === "jellyfin" || platform === "emby") {
      lines.push(configLine("PAIRCUE_SERVER_USER_ID", value("server-user-id")));
    }
  }

  lines.push(
    "",
    "# The learning pair",
    configLine("PAIRCUE_SOURCE_LANGUAGE", value("source-language")),
    configLine("PAIRCUE_TARGET_LANGUAGE", value("target-language")),
    configLine("PAIRCUE_TARGET_LANGUAGE_STYLE", value("target-style")),
    configLine("PAIRCUE_BILINGUAL_ORDER", value("line-order")),
    configLine("PAIRCUE_SYNC_ENABLED", "true"),
    configLine("PAIRCUE_CLEAN_SOURCE_OUTPUT", "true"),
    "",
    "# Exact-release subtitle search",
    configLine("PAIRCUE_SUBTITLE_DOWNLOAD_ENABLED", String(checked("search-enabled"))),
    configLine(
      "PAIRCUE_OPENSUBTITLES_API_KEY",
      secretValue("opensubtitles-key", maskSecrets),
    ),
    "",
    "# Translation",
    configLine("PAIRCUE_TRANSLATION_ENABLED", String(checked("translation-enabled"))),
    configLine("PAIRCUE_TRANSLATION_BASE_URL", value("translation-url")),
    configLine("PAIRCUE_TRANSLATION_API_KEY", secretValue("translation-key", maskSecrets)),
    configLine("PAIRCUE_TRANSLATION_MODEL", value("translation-model")),
    "",
    "# Speech transcription fallback",
    configLine("PAIRCUE_TRANSCRIPTION_ENABLED", String(checked("transcription-enabled"))),
    configLine("PAIRCUE_TRANSCRIPTION_BASE_URL", value("transcription-url")),
    configLine("PAIRCUE_TRANSCRIPTION_API_KEY", secretValue("transcription-key", maskSecrets)),
    configLine("PAIRCUE_TRANSCRIPTION_MODEL", value("transcription-model")),
    "",
    "# Local-only service access",
    configLine("PAIRCUE_WEBHOOK_ENABLED", "false"),
    configLine("PAIRCUE_API_HOST", mode === "library" ? "0.0.0.0" : "127.0.0.1"),
    configLine("PAIRCUE_API_PORT", "9292"),
    configLine("PAIRCUE_API_TOKEN", maskSecrets ? "•••••••• (generated in download)" : apiToken),
    configLine("PAIRCUE_TRUSTED_HOSTS", "localhost,127.0.0.1"),
  );
  return `${lines.join("\n")}\n`;
}

function updateMode() {
  const library = selectedMode() === "library";
  byId("library-options").hidden = !library;
  byId("single-note").hidden = library;
  byId("download-config").textContent = library ? "Save paircue.env" : "Save and choose a video";
  updatePlatform();
  updateNextStep();
}

function updateSubtitlePreset() {
  const preset = form.querySelector('input[name="subtitle-preset"]:checked').value;
  const choices = {
    both: { search: false, translation: false },
    one: { search: false, translation: true },
    automatic: { search: true, translation: true },
  };
  byId("search-enabled").checked = choices[preset].search;
  byId("translation-enabled").checked = choices[preset].translation;
  byId("transcription-enabled").checked = false;
  setPanelEnabled("search-enabled", "search-panel");
  setPanelEnabled("translation-enabled", "translation-panel");
  setPanelEnabled("transcription-enabled", "transcription-panel");
}

function setPanelEnabled(toggleId, panelId) {
  const enabled = checked(toggleId);
  const panel = byId(panelId);
  panel.hidden = !enabled;
  panel.querySelectorAll("input").forEach((input) => {
    input.disabled = !enabled;
  });
}

function updatePlatform() {
  const platform = selectedPlatform();
  const isFolder = selectedMode() === "single" || platform === "filesystem";
  const needsUser = platform === "jellyfin" || platform === "emby";
  byId("server-fields").hidden = isFolder;
  byId("user-id-field").hidden = !needsUser;
  byId("server-url").disabled = isFolder;
  byId("server-token").disabled = isFolder;
  byId("server-prefix").disabled = isFolder;
  byId("server-user-id").disabled = !needsUser;
  if (!isFolder) {
    const defaults = {
      plex: "http://plex:32400",
      jellyfin: "http://jellyfin:8096",
      emby: "http://emby:8096",
    };
    byId("server-url").value = defaults[platform];
  }
}

function clearValidity() {
  form.querySelectorAll("input").forEach((input) => input.setCustomValidity(""));
  formError.hidden = true;
  formError.textContent = "";
}

function requireField(id, message) {
  const input = byId(id);
  if (!input.disabled && !value(id)) {
    input.setCustomValidity(message);
    return false;
  }
  return true;
}

function validate() {
  clearValidity();
  let valid = true;
  const mode = selectedMode();
  const platform = selectedPlatform();
  if (mode === "library") {
    valid = requireField("host-media-path", "Enter the media folder on this machine or NAS.") && valid;
    valid = requireField("host-port", "Enter the local status page port.") && valid;
    valid = requireField("puid", "Enter the container user ID.") && valid;
    valid = requireField("pgid", "Enter the container group ID.") && valid;
    const port = Number(value("host-port"));
    if (!Number.isInteger(port) || port < 1 || port > 65535) {
      byId("host-port").setCustomValidity("Use a port between 1 and 65535.");
      valid = false;
    }
  }
  if (mode === "library" && platform !== "filesystem") {
    valid = requireField("server-url", "Enter the server address.") && valid;
    valid = requireField("server-token", "Enter the server token or API key.") && valid;
    valid = requireField("server-prefix", "Enter the library path seen by the server.") && valid;
  }
  if (mode === "library" && (platform === "jellyfin" || platform === "emby")) {
    valid = requireField("server-user-id", "Enter the user ID.") && valid;
  }
  valid = requireField("source-language", "Enter the spoken language.") && valid;
  valid = requireField("target-language", "Enter the learning language.") && valid;
  valid = requireField("target-style", "Describe the subtitle writing style.") && valid;
  const languageTag = /^[A-Za-z]{2,8}(?:-[A-Za-z0-9]{1,8})*$/;
  if (!languageTag.test(value("source-language"))) {
    byId("source-language").setCustomValidity("Use a language tag such as en, ja, or zh-HK.");
    valid = false;
  }
  if (!languageTag.test(value("target-language"))) {
    byId("target-language").setCustomValidity("Use a language tag such as en, ja, or zh-HK.");
    valid = false;
  }
  if (value("source-language").toLowerCase() === value("target-language").toLowerCase()) {
    byId("target-language").setCustomValidity("Choose two different languages.");
    valid = false;
  }
  if (checked("search-enabled")) {
    valid = requireField("opensubtitles-key", "Add your OpenSubtitles API key or disable search.") && valid;
  }
  if (checked("translation-enabled")) {
    valid = requireField("translation-url", "Enter the translation endpoint.") && valid;
    valid = requireField("translation-key", "Add the translation API key or disable translation.") && valid;
    valid = requireField("translation-model", "Enter the translation model.") && valid;
  }
  if (checked("transcription-enabled")) {
    valid = requireField("transcription-url", "Enter the transcription endpoint.") && valid;
    valid = requireField("transcription-model", "Enter the transcription model.") && valid;
    try {
      const host = new URL(value("transcription-url")).hostname;
      if (host === "api.openai.com") {
        valid = requireField(
          "transcription-key",
          "OpenAI transcription requires an API key.",
        ) && valid;
      }
    } catch {
      byId("transcription-url").setCustomValidity("Enter a valid transcription URL.");
      valid = false;
    }
  }
  if (!valid || !form.checkValidity()) {
    formError.textContent = "Check the highlighted fields, then try again.";
    formError.hidden = false;
    form.reportValidity();
    return false;
  }
  return true;
}

function updatePreview() {
  try {
    preview.textContent = buildConfig(true);
  } catch (error) {
    preview.textContent = `Configuration preview unavailable: ${error.message}`;
  }
}

function updateNextStep() {
  const library = selectedMode() === "library";
  byId("next-step").removeAttribute("data-phase");
  byId("next-number").textContent = "NEXT";
  if (library) {
    byId("next-heading").textContent = "Start the library service";
    byId("next-copy").textContent = "Put paircue.env beside docker-compose.yml, then run:";
    byId("next-command").textContent = [
      "docker compose --env-file paircue.env build core",
      "docker compose --env-file paircue.env run --rm core paircue doctor",
      "docker compose --env-file paircue.env up -d core",
    ].join("\n");
    return;
  }
  byId("next-heading").textContent = "Try one video";
  byId("next-copy").textContent =
    "After saving, PairCue opens your system file chooser. Pick one video and it starts for you.";
  byId("next-command").textContent = "Later: paircue learn --config paircue.env";
}

function configForAction() {
  if (!validate()) {
    return null;
  }
  try {
    return buildConfig(false);
  } catch (error) {
    formError.textContent = error.message;
    formError.hidden = false;
    return null;
  }
}

async function copyConfig() {
  const config = configForAction();
  if (config === null) {
    return;
  }
  try {
    await navigator.clipboard.writeText(config);
  } catch {
    const helper = document.createElement("textarea");
    helper.value = config;
    helper.setAttribute("readonly", "");
    helper.style.position = "fixed";
    helper.style.opacity = "0";
    document.body.append(helper);
    helper.select();
    document.execCommand("copy");
    helper.remove();
  }
  actionStatus.textContent = "Configuration copied. Keep it somewhere private.";
}

function downloadConfigFile(config) {
  const url = URL.createObjectURL(new Blob([config], { type: "text/plain;charset=utf-8" }));
  const link = document.createElement("a");
  link.href = url;
  link.download = "paircue.env";
  document.body.append(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
  actionStatus.textContent = "paircue.env downloaded. Do not commit this file to GitHub.";
}

async function saveConfig() {
  const config = configForAction();
  if (config === null) {
    return;
  }
  const token = new URLSearchParams(window.location.search).get("token");
  if (!window.location.protocol.startsWith("http") || !token) {
    downloadConfigFile(config);
    return;
  }
  const button = byId("download-config");
  button.disabled = true;
  button.textContent = "Saving…";
  try {
    const response = await fetch(`/config?token=${encodeURIComponent(token)}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ config, mode: selectedMode() }),
    });
    const payload = await response.json();
    if (!response.ok || !payload.saved) {
      throw new Error(payload.message || "PairCue could not save the setup.");
    }
    button.textContent = "Saved";
    actionStatus.textContent = payload.backup
      ? `Saved in ${payload.location}. Your previous file was backed up as ${payload.backup}.`
      : `Saved ${payload.filename} in ${payload.location}.`;
    if (selectedMode() === "single") {
      actionStatus.textContent = `Saved ${payload.filename}. Look for the video file window.`;
      pollProgress(token);
    }
  } catch (error) {
    button.disabled = false;
    button.textContent = selectedMode() === "library" ? "Save paircue.env" : "Save and choose a video";
    formError.textContent = `${error.message} You can still use “Copy config”.`;
    formError.hidden = false;
  }
}

function renderProgress(payload) {
  const panel = byId("next-step");
  const number = byId("next-number");
  const heading = byId("next-heading");
  const copy = byId("next-copy");
  const output = byId("next-command");
  panel.dataset.phase = payload.phase;
  output.textContent = Array.isArray(payload.outputs) ? payload.outputs.join("\n") : "";

  if (payload.phase === "choosing") {
    number.textContent = "1";
    heading.textContent = "Choose one video";
    copy.textContent = payload.message;
    return;
  }
  if (payload.phase === "processing" || payload.phase === "saved") {
    number.textContent = "•••";
    heading.textContent = "PairCue is working";
    copy.textContent = payload.message;
    return;
  }
  if (payload.phase === "completed") {
    number.textContent = "DONE";
    heading.textContent = "Your bilingual subtitle is ready";
    copy.textContent = `${payload.message} The finished file is highlighted in your file manager.`;
    return;
  }
  if (payload.phase === "cancelled") {
    number.textContent = "SAVED";
    heading.textContent = "Your setup is ready for later";
    copy.textContent = payload.message;
    return;
  }
  if (payload.phase === "failed") {
    number.textContent = "CHECK";
    heading.textContent = "PairCue needs one more thing";
    copy.textContent = payload.message;
  }
}

async function pollProgress(token) {
  while (true) {
    try {
      const response = await fetch(`/progress?token=${encodeURIComponent(token)}`, {
        headers: { Accept: "application/json" },
      });
      const payload = await response.json();
      if (!response.ok) {
        throw new Error("progress check failed");
      }
      renderProgress(payload);
      if (payload.terminal) {
        return;
      }
    } catch {
      byId("next-step").dataset.phase = "failed";
      byId("next-number").textContent = "CHECK";
      byId("next-heading").textContent = "PairCue stopped reporting progress";
      byId("next-copy").textContent =
        "Your setup is saved. Reopen PairCue to check the video or try again.";
      return;
    }
    await new Promise((resolve) => window.setTimeout(resolve, 650));
  }
}

async function updateSystemReadiness() {
  const status = byId("system-check");
  if (!window.location.protocol.startsWith("http")) {
    status.textContent = "PairCue checks the video tools when this page is opened from the app.";
    return;
  }
  try {
    const response = await fetch("/readiness", { headers: { Accept: "application/json" } });
    const payload = await response.json();
    if (!response.ok) {
      throw new Error("readiness check failed");
    }
    if (payload.ready) {
      status.dataset.status = "ready";
      status.textContent = "✓ This device is ready to read and align video.";
      return;
    }
    status.dataset.status = "needs-attention";
    status.textContent =
      "Optional video tools are missing. Search, translation, and two SRT tracks still work; embedded subtitles, timing alignment, and speech generation need FFmpeg.";
  } catch {
    status.textContent = "PairCue could not check the video tools. Setup can still continue.";
  }
}

form.addEventListener("input", () => {
  clearValidity();
  updatePreview();
  updateNextStep();
});

form.querySelectorAll('input[name="mode"]').forEach((input) => {
  input.addEventListener("change", () => {
    updateMode();
    updatePreview();
  });
});

form.querySelectorAll('input[name="platform"]').forEach((input) => {
  input.addEventListener("change", () => {
    updatePlatform();
    updatePreview();
  });
});

form.querySelectorAll('input[name="subtitle-preset"]').forEach((input) => {
  input.addEventListener("change", () => {
    updateSubtitlePreset();
    updatePreview();
  });
});

[
  ["search-enabled", "search-panel"],
  ["translation-enabled", "translation-panel"],
  ["transcription-enabled", "transcription-panel"],
].forEach(([toggleId, panelId]) => {
  byId(toggleId).addEventListener("change", () => {
    setPanelEnabled(toggleId, panelId);
    updatePreview();
  });
  setPanelEnabled(toggleId, panelId);
});

byId("swap-languages").addEventListener("click", () => {
  const source = byId("source-language");
  const target = byId("target-language");
  [source.value, target.value] = [target.value, source.value];
  updatePreview();
});

byId("copy-config").addEventListener("click", copyConfig);
byId("download-config").addEventListener("click", saveConfig);

secretIds.forEach((id) => {
  byId(id).addEventListener("paste", () => {
    actionStatus.textContent = "Secret added locally. It will be hidden from the preview.";
  });
});

updateMode();
updatePreview();
updateSystemReadiness();
