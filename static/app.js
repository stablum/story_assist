const defaultQuestions = [
  "What key background facts should a reader understand before this story?",
  "What are 3-5 plausible investigative angles that are not obvious from the sketch?",
  "Which public records, datasets, or institutions are most relevant to verify this story?",
  "What timeline of events is likely and which dates should be confirmed first?",
];

const TOKEN_STORAGE_KEY = "storyAssistApiToken";

const form = document.getElementById("analyze-form");
const apiTokenInput = document.getElementById("api-token");
const storySketch = document.getElementById("story-sketch");
const questionPreambleInput = document.getElementById("question-preamble");
const providerInput = document.getElementById("provider");
const modelSelect = document.getElementById("model");
const modelNote = document.getElementById("model-note");
const reasoningEffortInput = document.getElementById("reasoning-effort");
const reasoningNote = document.getElementById("reasoning-note");
const questionsList = document.getElementById("questions-list");
const addQuestionButton = document.getElementById("add-question");
const analyzeButton = document.getElementById("analyze-button");
const statusEl = document.getElementById("status");
const answersEl = document.getElementById("answers");
const metaEl = document.getElementById("meta");
const progressJobIdEl = document.getElementById("progress-job-id");
const progressBarEl = document.getElementById("progress-bar");
const progressSummaryEl = document.getElementById("progress-summary");
const progressTimingEl = document.getElementById("progress-timing");
const progressListEl = document.getElementById("progress-list");

let questions = [...defaultQuestions];
let modelRequestCounter = 0;
let activeJobId = null;
let pollingTimer = null;

function setStatus(message, isError = false) {
  statusEl.textContent = message;
  statusEl.style.color = isError ? "#8d2118" : "#5f5249";
}

function getApiToken() {
  return apiTokenInput.value.trim();
}

function persistToken() {
  const token = getApiToken();
  if (!token) {
    localStorage.removeItem(TOKEN_STORAGE_KEY);
    return;
  }
  localStorage.setItem(TOKEN_STORAGE_KEY, token);
}

function restoreToken() {
  const token = localStorage.getItem(TOKEN_STORAGE_KEY) || "";
  apiTokenInput.value = token;
}

async function apiFetchJson(url, options = {}) {
  const token = getApiToken();
  if (!token) {
    throw new Error("API token required. Set APP_API_TOKEN and paste it in the UI.");
  }

  const requestOptions = {
    ...options,
    headers: {
      ...(options.headers || {}),
      Authorization: `Bearer ${token}`,
    },
  };

  const response = await fetch(url, requestOptions);

  let body = {};
  try {
    body = await response.json();
  } catch {
    body = {};
  }

  return { response, body };
}

function renderQuestions() {
  questionsList.innerHTML = "";

  questions.forEach((question, index) => {
    const wrapper = document.createElement("div");
    wrapper.className = "question-item";

    const textarea = document.createElement("textarea");
    textarea.value = question;
    textarea.placeholder = "Write a question the model should answer";
    textarea.addEventListener("input", (event) => {
      questions[index] = event.target.value;
    });

    const removeButton = document.createElement("button");
    removeButton.type = "button";
    removeButton.textContent = "Remove";
    removeButton.addEventListener("click", () => {
      questions.splice(index, 1);
      renderQuestions();
    });

    wrapper.append(textarea, removeButton);
    questionsList.append(wrapper);
  });
}

function getCleanQuestions() {
  return questions.map((item) => item.trim()).filter(Boolean);
}

function setModelOptions(defaultModel, models, selectedValue) {
  const optionValues = Array.from(
    new Set([...(models || [])].filter((item) => typeof item === "string" && item.trim())),
  );

  modelSelect.innerHTML = "";

  const defaultOption = document.createElement("option");
  defaultOption.value = "";
  defaultOption.textContent = `Provider default (${defaultModel || "default"})`;
  modelSelect.append(defaultOption);

  optionValues.forEach((model) => {
    const option = document.createElement("option");
    option.value = model;
    option.textContent = model;
    modelSelect.append(option);
  });

  if (selectedValue && optionValues.includes(selectedValue)) {
    modelSelect.value = selectedValue;
  } else {
    modelSelect.value = "";
  }
}

async function loadDefaultQuestionPreamble() {
  if (questionPreambleInput.value.trim()) {
    return;
  }

  try {
    const response = await fetch("/api/defaults");
    if (!response.ok) {
      return;
    }

    const body = await response.json();
    if (
      !questionPreambleInput.value.trim()
      && typeof body.question_preamble_default === "string"
      && body.question_preamble_default.trim()
    ) {
      questionPreambleInput.value = body.question_preamble_default;
    }
  } catch {
    // Leave the field empty if the default cannot be loaded.
  }
}

async function loadModelOptions() {
  const token = getApiToken();
  if (!token) {
    modelSelect.disabled = true;
    setModelOptions("", [], "");
    modelNote.textContent = "Enter API token to load models.";
    return;
  }

  const requestId = ++modelRequestCounter;
  const provider = providerInput.value;
  const previousSelection = modelSelect.value;
  modelSelect.disabled = true;
  modelSelect.innerHTML = "<option value=\"\">Loading models...</option>";

  try {
    const { response, body } = await apiFetchJson(
      `/api/model-options?provider=${encodeURIComponent(provider)}`,
    );

    if (!response.ok) {
      throw new Error(body.detail || "Could not load models");
    }

    if (requestId !== modelRequestCounter) {
      return;
    }

    setModelOptions(body.default_model, body.models, previousSelection);
    modelNote.textContent = `Loaded ${body.models.length} options for ${provider}.`;
  } catch (error) {
    if (requestId !== modelRequestCounter) {
      return;
    }

    setModelOptions("", [], "");
    modelNote.textContent = `Could not load model list for ${provider}.`;
    setStatus(error.message || "Unable to load models", true);
  } finally {
    if (requestId === modelRequestCounter) {
      modelSelect.disabled = false;
    }
  }
}

function syncReasoningControl() {
  const isOpenAI = providerInput.value === "openai";
  reasoningEffortInput.disabled = !isOpenAI;
  reasoningNote.textContent = isOpenAI
    ? "Applies to OpenAI reasoning models."
    : "Ignored for this provider.";
}

function escapeHtml(text) {
  return text
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll("\"", "&quot;")
    .replaceAll("'", "&#039;");
}

function safeUrl(rawUrl) {
  try {
    const parsed = new URL(rawUrl, window.location.origin);
    if (parsed.protocol === "http:" || parsed.protocol === "https:") {
      return parsed.href;
    }
  } catch {
    return null;
  }
  return null;
}

function renderInlineMarkdown(source) {
  const segments = source.split(/`([^`]+)`/g);
  const rendered = segments.map((segment, index) => {
    if (index % 2 === 1) {
      return `<code>${escapeHtml(segment)}</code>`;
    }

    const linkTokens = [];
    let plain = segment.replace(/\[([^\]]+)\]\(([^)\s]+)\)/g, (match, label, url) => {
      const safe = safeUrl(url);
      if (!safe) {
        return match;
      }
      const token = `__LINK_TOKEN_${linkTokens.length}__`;
      linkTokens.push(
        `<a href="${escapeHtml(safe)}" target="_blank" rel="noopener noreferrer">${escapeHtml(label)}</a>`,
      );
      return token;
    });

    plain = escapeHtml(plain)
      .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
      .replace(/\*([^*]+)\*/g, "<em>$1</em>");

    linkTokens.forEach((tokenHtml, tokenIndex) => {
      plain = plain.replace(`__LINK_TOKEN_${tokenIndex}__`, tokenHtml);
    });

    return plain;
  });

  return rendered.join("");
}

function markdownToHtml(markdownText) {
  const source = (typeof markdownText === "string" ? markdownText : "").replace(/\r\n/g, "\n");
  const lines = source.split("\n");
  const html = [];
  const listItems = [];
  let inCodeBlock = false;
  const codeLines = [];

  const flushList = () => {
    if (!listItems.length) {
      return;
    }
    html.push(`<ul>${listItems.map((item) => `<li>${item}</li>`).join("")}</ul>`);
    listItems.length = 0;
  };

  const flushCodeBlock = () => {
    if (!codeLines.length) {
      html.push("<pre><code></code></pre>");
      return;
    }
    html.push(`<pre><code>${escapeHtml(codeLines.join("\n"))}</code></pre>`);
    codeLines.length = 0;
  };

  lines.forEach((line) => {
    if (line.trim().startsWith("```")) {
      flushList();
      if (!inCodeBlock) {
        inCodeBlock = true;
      } else {
        flushCodeBlock();
        inCodeBlock = false;
      }
      return;
    }

    if (inCodeBlock) {
      codeLines.push(line);
      return;
    }

    const trimmed = line.trim();
    if (!trimmed) {
      flushList();
      return;
    }

    const listMatch = trimmed.match(/^[-*]\s+(.+)$/);
    if (listMatch) {
      listItems.push(renderInlineMarkdown(listMatch[1]));
      return;
    }

    flushList();

    const headingMatch = trimmed.match(/^(#{1,4})\s+(.+)$/);
    if (headingMatch) {
      const level = headingMatch[1].length;
      html.push(`<h${level}>${renderInlineMarkdown(headingMatch[2])}</h${level}>`);
      return;
    }

    html.push(`<p>${renderInlineMarkdown(trimmed)}</p>`);
  });

  if (inCodeBlock) {
    flushCodeBlock();
  }
  flushList();

  return html.join("\n");
}

function renderMarkdownBlock(container, markdownText) {
  container.innerHTML = markdownToHtml(markdownText);
}

function renderAnswers(results) {
  answersEl.innerHTML = "";

  results.forEach((item) => {
    const card = document.createElement("article");
    card.className = "answer-card";

    const title = document.createElement("h4");
    title.textContent = item.question;

    if (item.error) {
      const errorText = document.createElement("p");
      errorText.className = "answer-error";
      errorText.textContent = `Error: ${item.error}`;
      card.append(title, errorText);
      answersEl.append(card);
      return;
    }

    const toolbar = document.createElement("div");
    toolbar.className = "answer-toolbar";

    const editButton = document.createElement("button");
    editButton.type = "button";
    editButton.textContent = "Edit Markdown";
    toolbar.append(editButton);

    const output = document.createElement("div");
    output.className = "answer-markdown";

    const rawInput = document.createElement("textarea");
    rawInput.className = "answer-raw";
    rawInput.value = item.answer || "";

    const rerender = () => {
      renderMarkdownBlock(output, rawInput.value);
    };
    rerender();

    editButton.addEventListener("click", () => {
      const willShow = !rawInput.classList.contains("is-visible");
      rawInput.classList.toggle("is-visible");
      editButton.textContent = willShow ? "Hide Editor" : "Edit Markdown";
      if (willShow) {
        rawInput.focus();
      }
    });

    rawInput.addEventListener("input", rerender);
    card.append(title, toolbar, output, rawInput);
    answersEl.append(card);
  });
}

function formatSeconds(secondsValue) {
  if (typeof secondsValue !== "number" || Number.isNaN(secondsValue)) {
    return "--";
  }
  return `${secondsValue.toFixed(1)}s`;
}

function formatStatus(status) {
  switch (status) {
    case "queued":
      return "Queued";
    case "running":
      return "Running";
    case "completed":
      return "Done";
    case "failed":
      return "Failed";
    case "completed_with_errors":
      return "Done w/ Errors";
    default:
      return status;
  }
}

function resetProgressPanel() {
  progressJobIdEl.textContent = "";
  progressBarEl.style.width = "0%";
  progressSummaryEl.textContent = "No run in progress.";
  progressTimingEl.textContent = "";
  progressListEl.innerHTML = "";
}

function renderProgress(progress) {
  progressJobIdEl.textContent = `Job ${progress.job_id.slice(0, 8)} | ${formatStatus(progress.status)}`;
  progressBarEl.style.width = `${progress.progress_percent || 0}%`;

  const doneCount = (progress.completed_questions || 0) + (progress.failed_questions || 0);
  progressSummaryEl.textContent = `${doneCount}/${progress.total_questions} finished | ${progress.failed_questions || 0} failed`;

  const runStart = typeof progress.started_at === "number" ? progress.started_at : null;
  const runEnd = typeof progress.finished_at === "number" ? progress.finished_at : null;
  if (runStart !== null) {
    const elapsed = Math.max(0, (runEnd ?? Date.now() / 1000) - runStart);
    progressTimingEl.textContent = `Elapsed: ${formatSeconds(elapsed)}`;
  } else {
    progressTimingEl.textContent = "";
  }

  progressListEl.innerHTML = "";
  (progress.items || []).forEach((item) => {
    const line = document.createElement("article");
    line.className = `progress-item ${item.status}`;

    const dot = document.createElement("span");
    dot.className = "progress-dot";

    const question = document.createElement("p");
    question.className = "progress-question";
    question.textContent = item.question;

    const right = document.createElement("p");
    right.className = "progress-right";

    const badge = document.createElement("span");
    badge.className = "progress-badge";
    badge.textContent = formatStatus(item.status);

    const timer = document.createElement("span");
    timer.textContent = formatSeconds(item.elapsed_seconds);

    right.append(badge, timer);
    line.append(dot, question, right);

    if (item.error) {
      const errorLine = document.createElement("p");
      errorLine.className = "progress-error";
      errorLine.textContent = `Error: ${item.error}`;
      line.append(errorLine);
    }

    progressListEl.append(line);
  });
}

function stopPolling() {
  if (pollingTimer !== null) {
    window.clearTimeout(pollingTimer);
    pollingTimer = null;
  }
}

function schedulePoll(jobId, delayMs = 650) {
  stopPolling();
  pollingTimer = window.setTimeout(() => {
    void pollJob(jobId);
  }, delayMs);
}

function isTerminalJobStatus(status) {
  return status === "completed" || status === "completed_with_errors";
}

function buildResultItems(progress) {
  return (progress.items || []).map((item) => ({
    question: item.question,
    answer: item.answer || "",
    error: item.error || null,
  }));
}

async function pollJob(jobId) {
  try {
    const { response, body } = await apiFetchJson(`/api/analyze/jobs/${encodeURIComponent(jobId)}`);

    if (!response.ok) {
      throw new Error(body.detail || "Could not fetch progress");
    }

    if (activeJobId !== jobId) {
      return;
    }

    renderProgress(body);
    const doneCount = (body.completed_questions || 0) + (body.failed_questions || 0);
    setStatus(`Running: ${doneCount}/${body.total_questions} complete`);

    if (!isTerminalJobStatus(body.status)) {
      schedulePoll(jobId);
      return;
    }

    stopPolling();
    renderAnswers(buildResultItems(body));

    const reasoningMeta = body.provider === "openai" && body.reasoning_effort
      ? ` | reasoning=${body.reasoning_effort}`
      : "";
    metaEl.textContent = `${body.provider} | ${body.model}${reasoningMeta}`;

    if ((body.failed_questions || 0) > 0) {
      setStatus(`Complete with ${body.failed_questions} failed question(s).`, true);
    } else {
      setStatus("Complete. You can edit outputs directly.");
    }

    analyzeButton.disabled = false;
    analyzeButton.textContent = "Analyze Story";
  } catch (error) {
    if (activeJobId !== jobId) {
      return;
    }

    setStatus(`Progress update failed: ${error.message || "unknown error"}`, true);
    schedulePoll(jobId, 1400);
  }
}

addQuestionButton.addEventListener("click", () => {
  questions.push("");
  renderQuestions();
});

apiTokenInput.addEventListener("input", () => {
  persistToken();
  void loadModelOptions();
});

providerInput.addEventListener("change", () => {
  syncReasoningControl();
  void loadModelOptions();
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();

  const token = getApiToken();
  const cleanedStory = storySketch.value.trim();
  const cleanedPreamble = questionPreambleInput.value.trim();
  const cleanedQuestions = getCleanQuestions();

  if (!token) {
    setStatus("API token required. Set APP_API_TOKEN and paste it above.", true);
    return;
  }

  if (!cleanedStory) {
    setStatus("Please provide a story sketch first.", true);
    return;
  }

  if (!cleanedQuestions.length) {
    setStatus("Add at least one non-empty question.", true);
    return;
  }

  stopPolling();
  activeJobId = null;
  resetProgressPanel();
  answersEl.innerHTML = "";

  const payload = {
    story_sketch: cleanedStory,
    question_preamble: cleanedPreamble || null,
    questions: cleanedQuestions,
    provider: providerInput.value,
    model: modelSelect.value || null,
    reasoning_effort: providerInput.value === "openai"
      ? reasoningEffortInput.value
      : null,
  };

  analyzeButton.disabled = true;
  analyzeButton.textContent = "Analyzing...";
  setStatus("Submitting analysis job...");
  metaEl.textContent = "";

  try {
    const { response, body } = await apiFetchJson("/api/analyze/jobs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      throw new Error(body.detail || "Analysis failed to start");
    }

    activeJobId = body.job_id;
    renderProgress({
      job_id: body.job_id,
      status: body.status,
      total_questions: payload.questions.length,
      completed_questions: 0,
      failed_questions: 0,
      progress_percent: 0,
      started_at: Date.now() / 1000,
      finished_at: null,
      items: payload.questions.map((question, index) => ({
        index,
        question,
        status: "queued",
        elapsed_seconds: null,
        error: null,
      })),
    });

    setStatus("Job started. Gathering live updates...");
    schedulePoll(body.job_id, 80);
  } catch (error) {
    analyzeButton.disabled = false;
    analyzeButton.textContent = "Analyze Story";
    setStatus(error.message || "Request failed", true);
  }
});

restoreToken();
renderQuestions();
syncReasoningControl();
resetProgressPanel();
void loadDefaultQuestionPreamble();
void loadModelOptions();




