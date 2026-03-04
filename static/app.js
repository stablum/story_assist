const defaultQuestions = [
  "What key background facts should a reader understand before this story?",
  "What are 3-5 plausible investigative angles that are not obvious from the sketch?",
  "Which public records, datasets, or institutions are most relevant to verify this story?",
  "What timeline of events is likely and which dates should be confirmed first?",
];

const form = document.getElementById("analyze-form");
const storySketch = document.getElementById("story-sketch");
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

let questions = [...defaultQuestions];
let modelRequestCounter = 0;

function setStatus(message, isError = false) {
  statusEl.textContent = message;
  statusEl.style.color = isError ? "#8d2118" : "#5f5249";
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

async function loadModelOptions() {
  const requestId = ++modelRequestCounter;
  const provider = providerInput.value;
  const previousSelection = modelSelect.value;
  modelSelect.disabled = true;
  modelSelect.innerHTML = "<option value=\"\">Loading models...</option>";

  try {
    const response = await fetch(`/api/model-options?provider=${encodeURIComponent(provider)}`);
    const body = await response.json();
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

function renderAnswers(results) {
  answersEl.innerHTML = "";

  results.forEach((item) => {
    const card = document.createElement("article");
    card.className = "answer-card";

    const title = document.createElement("h4");
    title.textContent = item.question;

    const output = document.createElement("textarea");
    output.value = item.error
      ? `Error: ${item.error}`
      : item.answer;

    if (item.error) {
      output.classList.add("answer-error");
    }

    card.append(title, output);
    answersEl.append(card);
  });
}

addQuestionButton.addEventListener("click", () => {
  questions.push("");
  renderQuestions();
});

providerInput.addEventListener("change", () => {
  syncReasoningControl();
  void loadModelOptions();
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();

  const cleanedStory = storySketch.value.trim();
  const cleanedQuestions = getCleanQuestions();

  if (!cleanedStory) {
    setStatus("Please provide a story sketch first.", true);
    return;
  }

  if (!cleanedQuestions.length) {
    setStatus("Add at least one non-empty question.", true);
    return;
  }

  analyzeButton.disabled = true;
  analyzeButton.textContent = "Analyzing...";
  setStatus("Running web-backed research prompts...");
  metaEl.textContent = "";

  try {
    const response = await fetch("/api/analyze", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        story_sketch: cleanedStory,
        questions: cleanedQuestions,
        provider: providerInput.value,
        model: modelSelect.value || null,
        reasoning_effort:
          providerInput.value === "openai"
            ? reasoningEffortInput.value
            : null,
      }),
    });

    const body = await response.json();
    if (!response.ok) {
      throw new Error(body.detail || "Analysis failed");
    }

    renderAnswers(body.results || []);
    const reasoningMeta = providerInput.value === "openai"
      ? ` | reasoning=${reasoningEffortInput.value}`
      : "";
    metaEl.textContent = `${body.provider} | ${body.model || "default model"}${reasoningMeta}`;
    setStatus("Complete. You can edit outputs directly.");
  } catch (error) {
    setStatus(error.message || "Request failed", true);
  } finally {
    analyzeButton.disabled = false;
    analyzeButton.textContent = "Analyze Story";
  }
});

renderQuestions();
syncReasoningControl();
void loadModelOptions();
