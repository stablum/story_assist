const defaultQuestions = [
  "What key background facts should a reader understand before this story?",
  "What are 3-5 plausible investigative angles that are not obvious from the sketch?",
  "Which public records, datasets, or institutions are most relevant to verify this story?",
  "What timeline of events is likely and which dates should be confirmed first?",
];

const form = document.getElementById("analyze-form");
const storySketch = document.getElementById("story-sketch");
const providerInput = document.getElementById("provider");
const modelInput = document.getElementById("model");
const questionsList = document.getElementById("questions-list");
const addQuestionButton = document.getElementById("add-question");
const analyzeButton = document.getElementById("analyze-button");
const statusEl = document.getElementById("status");
const answersEl = document.getElementById("answers");
const metaEl = document.getElementById("meta");

let questions = [...defaultQuestions];

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
        model: modelInput.value.trim() || null,
      }),
    });

    const body = await response.json();
    if (!response.ok) {
      throw new Error(body.detail || "Analysis failed");
    }

    renderAnswers(body.results || []);
    metaEl.textContent = `${body.provider} | ${body.model || "default model"}`;
    setStatus("Complete. You can edit outputs directly.");
  } catch (error) {
    setStatus(error.message || "Request failed", true);
  } finally {
    analyzeButton.disabled = false;
    analyzeButton.textContent = "Analyze Story";
  }
});

renderQuestions();