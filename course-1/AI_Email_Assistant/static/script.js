const form = document.getElementById("email-form");
const spinner = document.getElementById("spinner");
const results = document.getElementById("results");
const resultCards = document.getElementById("result-cards");
const generateBtn = document.getElementById("generate-btn");

const MODEL_KEYS = Array.from(document.getElementById("model").options)
    .map((o) => o.value)
    .filter((v) => v !== "all");

async function postGenerate(modelKey, payload) {
    const res = await fetch("/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ...payload, model: modelKey }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Request failed");
    return data;
}

function subjectQuality(subject) {
    let score = 0;
    const len = subject.trim().length;
    if (len >= 8 && len <= 90) score += 4;
    if (subject[0] === subject[0].toUpperCase() && subject[0] !== subject[0].toLowerCase()) score += 3;
    if (!/[.?!]$/.test(subject.trim())) score += 3;
    return Math.min(10, score);
}

function renderCard(modelKey, data) {
    const len = (data.email || "").length;
    const quality = subjectQuality(data.subject || "");
    const card = document.createElement("article");
    card.className = "email-card";

    card.innerHTML = `
        <h3>${modelKey.toUpperCase()}</h3>
        <div class="email-subject">${escapeHtml(data.subject)}</div>
        <span class="tone-label">${escapeHtml(data.tone)}</span>
        <div class="email-body">${escapeHtml(data.email)}</div>
        <div class="improvements">
            <p>Suggestions</p>
            <ul>${(data.improvements || []).map((i) => `<li>${escapeHtml(i)}</li>`).join("")}</ul>
        </div>
        <div class="metrics">
            <span class="metric">Time: ${data.duration_ms} ms</span>
            <span class="metric">Length: ${len} chars</span>
            <span class="metric">Subject quality: ${quality}/10</span>
        </div>`;
    return card;
}

function escapeHtml(value) {
    const div = document.createElement("div");
    div.textContent = value;
    return div.innerHTML;
}

form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const payload = {
        topic: document.getElementById("topic").value.trim(),
        tone: document.getElementById("tone").value,
        email_type: document.getElementById("email_type").value,
    };

    if (!payload.topic) return;

    const model = document.getElementById("model").value;
    const targets = model === "all" ? MODEL_KEYS : [model];

    generateBtn.disabled = true;
    spinner.classList.remove("hidden");
    results.classList.add("hidden");
    resultCards.innerHTML = "";

    try {
        const outputs = await Promise.all(
            targets.map((key) =>
                postGenerate(key, payload).catch((err) => ({
                    error: err.message,
                    model_key: key,
                }))
            )
        );

        if (outputs.some((o) => o.error)) {
            const err = document.createElement("div");
            err.className = "error";
            err.textContent = outputs
                .filter((o) => o.error)
                .map((o) => `${o.model_key}: ${o.error}`)
                .join("\n");
            resultCards.appendChild(err);
        }

        outputs
            .filter((o) => !o.error)
            .forEach((data, i) => resultCards.appendChild(renderCard(targets[i], data)));

        results.classList.remove("hidden");
    } catch (err) {
        const errEl = document.createElement("div");
        errEl.className = "error";
        errEl.textContent = err.message;
        resultCards.appendChild(errEl);
        results.classList.remove("hidden");
    } finally {
        spinner.classList.add("hidden");
        generateBtn.disabled = false;
    }
});