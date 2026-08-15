const form = document.getElementById('chat-form');
const input = document.getElementById('message-input');
const modelSelect = document.getElementById('model-select');
const messages = document.getElementById('messages');
const emptyState = document.getElementById('empty-state');
const sendBtn = document.getElementById('send-btn');

function scrollToBottom() {
    messages.scrollTop = messages.scrollHeight;
}

function hideEmptyState() {
    if (emptyState) emptyState.style.display = 'none';
}

function addUserBubble(text) {
    const row = document.createElement('div');
    row.className = 'bubble-row user';
    row.innerHTML = `
        <span class="bubble-label">You</span>
        <div class="bubble user"></div>
    `;
    row.querySelector('.bubble').textContent = text;
    messages.appendChild(row);
    scrollToBottom();
}

function addLoadingBubble(modelLabel) {
    const row = document.createElement('div');
    row.className = 'bubble-row assistant loading';
    row.innerHTML = `
        <span class="bubble-label">${modelLabel}</span>
        <div class="bubble assistant">Thinking…</div>
    `;
    messages.appendChild(row);
    scrollToBottom();
    return row;
}

function renderAssistantBubble(row, modelLabel, data) {
    row.classList.remove('loading');

    if (data.error) {
        row.innerHTML = `
            <span class="bubble-label">${modelLabel}</span>
            <div class="bubble error">${escapeHtml(data.error)}</div>
        `;
        return;
    }

    const sentiment = Number(data.sentiment ?? 0);
    const duration = data.duration ? `${data.duration.toFixed(2)}s` : '';

    row.innerHTML = `
        <span class="bubble-label">${modelLabel}</span>
        <div class="bubble assistant">
            <div class="ai-response-field">
                <span class="field-key">Summary</span>
                <span class="field-val">${escapeHtml(data.summary ?? '')}</span>
            </div>
            <div class="ai-response-field">
                <span class="field-key">Sentiment</span>
                <div class="field-val sentiment-bar">
                    <div class="sentiment-track">
                        <div class="sentiment-fill" style="width:${sentiment}%"></div>
                    </div>
                    <span class="meta">${sentiment}/100</span>
                </div>
            </div>
            <div class="ai-response-field">
                <span class="field-key">Response</span>
                <span class="field-val">${escapeHtml(data.response ?? '')}</span>
            </div>
            ${duration ? `<div class="meta" style="margin-top:8px;">${duration}</div>` : ''}
        </div>
    `;
    scrollToBottom();
}

function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

function modelLabel(value) {
    return { llama: 'Llama', granite: 'Granite', mistral: 'Mistral' }[value] || value;
}

function autoResize() {
    input.style.height = 'auto';
    input.style.height = Math.min(input.scrollHeight, 140) + 'px';
}
input.addEventListener('input', autoResize);

input.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        form.requestSubmit();
    }
});

form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const text = input.value.trim();
    if (!text) return;

    const model = modelSelect.value;

    hideEmptyState();
    addUserBubble(text);
    input.value = '';
    autoResize();
    sendBtn.disabled = true;

    const loadingRow = addLoadingBubble(modelLabel(model));

    try {
        const res = await fetch('/generate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: text, model }),
        });
        const data = await res.json();
        renderAssistantBubble(loadingRow, modelLabel(model), data);
    } catch (err) {
        renderAssistantBubble(loadingRow, modelLabel(model), { error: 'Network error: ' + err.message });
    } finally {
        sendBtn.disabled = false;
        input.focus();
    }
});
