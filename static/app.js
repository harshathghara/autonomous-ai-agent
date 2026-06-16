const stepsEl = document.getElementById("steps");
const taskListEl = document.getElementById("task-list");
const form = document.getElementById("chat-form");
const promptEl = document.getElementById("prompt");
const submitBtn = document.getElementById("submit-btn");
const autoApproveEl = document.getElementById("auto-approve");
const viewAllBtn = document.getElementById("view-all-btn");
const bannerEl = document.getElementById("banner");
const bannerTextEl = bannerEl.querySelector(".banner-text");
const manageConnectionEl = document.getElementById("manage-connection");
const newChatBtn = document.getElementById("new-chat-btn");

let activeTaskId = null;
let socket = null;
let allTasks = [];
let taskListLimit = 8;

const ICONS = {
  user: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>`,
  rocket: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4.5 16.5c-1.5 1.26-2 5-2 5s3.74-.5 5-2c.71-.84.7-2.13-.09-2.91a2.18 2.18 0 0 0-2.91-.09z"/><path d="M12 15l-3-3a22 22 0 0 1 2-3.95A12.88 12.88 0 0 1 22 2c0 2.72-.78 7.5-6 11a22.35 22.35 0 0 1-4 2z"/><path d="M9 12H4s.55-3.03 2-4c1.62-1.08 5 0 5 0"/><path d="M12 15v5s3.03-.55 4-2c1.08-1.62 0-5 0-5"/></svg>`,
  thought: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 18h6"/><path d="M10 22h4"/><path d="M12 2a7 7 0 0 0-4 12.74V17h8v-2.26A7 7 0 0 0 12 2z"/></svg>`,
  tool: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"/></svg>`,
  result: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M3 5v14a9 3 0 0 0 18 0V5"/><path d="M3 12a9 3 0 0 0 18 0"/></svg>`,
  final: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>`,
  error: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>`,
  confirm: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>`,
  copy: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>`,
  completed: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>`,
  running: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/></svg>`,
  failed: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>`,
  delete: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/><path d="M10 11v6M14 11v6"/><path d="M9 6V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2"/></svg>`,
};

function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}

function getTimeline() {
  let tl = stepsEl.querySelector(".timeline");
  if (!tl) {
    stepsEl.innerHTML = "";
    tl = document.createElement("div");
    tl.className = "timeline";
    stepsEl.appendChild(tl);
  }
  return tl;
}

function highlightJson(raw) {
  const text = typeof raw === "string" ? raw : JSON.stringify(raw, null, 2);
  return escapeHtml(text)
    .replace(/"([^"\\]*(\\.[^"\\]*)*)"(?=\s*:)/g, '<span class="json-key">"$1"</span>')
    .replace(/:\s*"([^"\\]*(\\.[^"\\]*)*)"/g, ': <span class="json-string">"$1"</span>')
    .replace(/:\s*(-?\d+(?:\.\d+)?(?:[eE][+\-]?\d+)?)/g, ': <span class="json-number">$1</span>')
    .replace(/:\s*(true|false)/g, ': <span class="json-bool">$1</span>')
    .replace(/:\s*(null)/g, ': <span class="json-null">$1</span>');
}

function codeBlock(content, rawForCopy) {
  const raw = rawForCopy ?? content;
  const copyText = typeof raw === "string" ? raw : JSON.stringify(raw, null, 2);
  let highlighted;
  if (typeof content === "object" && content !== null) {
    highlighted = highlightJson(content);
  } else if (
    typeof content === "string" &&
    (content.trim().startsWith("{") || content.trim().startsWith("["))
  ) {
    highlighted = highlightJson(content);
  } else {
    highlighted = escapeHtml(String(content ?? ""));
  }

  const wrap = document.createElement("div");
  wrap.className = "code-block";
  wrap.innerHTML = `<pre>${highlighted}</pre>`;
  const btn = document.createElement("button");
  btn.type = "button";
  btn.className = "btn-copy";
  btn.title = "Copy";
  btn.innerHTML = ICONS.copy;
  btn.addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(copyText);
      btn.title = "Copied!";
      setTimeout(() => {
        btn.title = "Copy";
      }, 1500);
    } catch {
      /* ignore */
    }
  });
  wrap.appendChild(btn);
  return wrap;
}

function iconForType(type) {
  const map = {
    user: ICONS.user,
    task_started: ICONS.rocket,
    thought: ICONS.thought,
    tool_call: ICONS.tool,
    tool_result: ICONS.result,
    final: ICONS.final,
    error: ICONS.error,
    confirmation_required: ICONS.confirm,
  };
  return map[type] || ICONS.thought;
}

function appendTimelineItem(type, label, bodyEl) {
  const tl = getTimeline();
  const item = document.createElement("div");
  item.className = "timeline-item";

  const icon = document.createElement("div");
  icon.className = "timeline-icon";
  icon.innerHTML = iconForType(type);

  const card = document.createElement("div");
  card.className = `event ${type}`;
  card.innerHTML = `<div class="event-header"><div class="label">${escapeHtml(label)}</div></div>`;
  card.appendChild(bodyEl);

  item.appendChild(icon);
  item.appendChild(card);
  tl.appendChild(item);
  stepsEl.scrollTop = stepsEl.scrollHeight;
  return card;
}

function addEvent(event) {
  let label = event.type.replace(/_/g, " ");
  const body = document.createElement("div");

  if (event.type === "thought" || event.type === "final") {
    label = event.type === "thought" ? "Thought" : "Final answer";
    body.className = "event-body";
    body.textContent = event.content || "";
  } else if (event.type === "tool_call") {
    label = `Tool call: ${event.name}`;
    body.appendChild(codeBlock(event.input, event.input));
  } else if (event.type === "tool_result") {
    label = `Tool result: ${event.name}`;
    const content = (event.content || "").slice(0, 4000);
    body.appendChild(codeBlock(content, content));
  } else if (event.type === "error") {
    label = "Error";
    body.className = "event-body";
    body.textContent = event.message || "Unknown error";
  } else if (event.type === "task_started") {
    label = "Task started";
    body.className = "event-body";
    body.textContent = event.input || "";
  } else if (event.type === "user") {
    label = "You";
    body.className = "event-body";
    body.textContent = event.content || "";
  } else {
    body.className = "event-body";
    body.textContent = JSON.stringify(event, null, 2);
  }

  appendTimelineItem(event.type, label, body);
}

function showConfirmationPrompt(event) {
  const body = document.createElement("div");
  const tool = escapeHtml(event.tool || "action");
  body.appendChild(codeBlock(event.input, event.input));

  const actions = document.createElement("div");
  actions.className = "confirm-actions";
  actions.innerHTML = `
    <button type="button" class="btn-approve">Approve</button>
    <button type="button" class="btn-deny">Deny</button>
  `;
  body.appendChild(actions);

  const card = appendTimelineItem(
    "confirmation_required",
    `Approval required: ${tool}`,
    body
  );

  card.querySelector(".btn-approve").addEventListener("click", () => {
    if (socket && socket.readyState === WebSocket.OPEN) {
      socket.send(
        JSON.stringify({
          type: "confirmation_response",
          confirmation_id: event.confirmation_id,
          approved: true,
        })
      );
    }
    card.closest(".timeline-item").remove();
  });
  card.querySelector(".btn-deny").addEventListener("click", () => {
    if (socket && socket.readyState === WebSocket.OPEN) {
      socket.send(
        JSON.stringify({
          type: "confirmation_response",
          confirmation_id: event.confirmation_id,
          approved: false,
        })
      );
    }
    card.closest(".timeline-item").remove();
  });
}

function addUserMessage(text) {
  addEvent({ type: "user", content: text });
}

function formatRelativeTime(iso) {
  if (!iso) return "";
  const date = new Date(iso);
  const now = new Date();
  const diffMs = now - date;
  const diffMin = Math.floor(diffMs / 60000);
  const diffHr = Math.floor(diffMs / 3600000);
  const time = date.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });

  if (diffMin < 1) return "Just now";
  if (diffMin < 60) return time;
  if (diffHr < 24 && date.getDate() === now.getDate()) return time;
  if (diffHr < 48) return "Yesterday";
  return date.toLocaleDateString([], { month: "short", day: "numeric" });
}

function statusLabel(status) {
  if (status === "completed") return "completed";
  if (status === "failed") return "failed";
  return "running";
}

function renderTaskList() {
  taskListEl.innerHTML = "";
  const visible = allTasks.slice(0, taskListLimit);

  visible.forEach((task) => {
    const li = document.createElement("li");
    li.className = "task-item";

    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "task-card";
    if (task.id === activeTaskId) btn.classList.add("active");

    const iconClass =
      task.status === "completed" ? "completed" : task.status === "failed" ? "failed" : "running";
    const iconKey =
      task.status === "completed" ? "completed" : task.status === "failed" ? "failed" : "running";

    const preview = task.input.length > 52 ? task.input.slice(0, 52) + "…" : task.input;
    const msgCount = task.message_count > 1 ? `${task.message_count} messages · ` : "";
    btn.innerHTML = `
      <span class="task-card-icon ${iconClass}">${ICONS[iconKey]}</span>
      <span class="task-card-body">
        <span class="task-card-preview">${escapeHtml(preview)}</span>
        <span class="task-card-meta">
          <span>${msgCount}${escapeHtml(statusLabel(task.status))}</span>
          <span class="dot">·</span>
          <span>${escapeHtml(formatRelativeTime(task.completed_at || task.created_at))}</span>
        </span>
      </span>
    `;
    btn.addEventListener("click", () => loadTaskDetail(task.id));

    const delBtn = document.createElement("button");
    delBtn.type = "button";
    delBtn.className = "task-delete";
    delBtn.title = "Delete chat";
    delBtn.setAttribute("aria-label", "Delete chat");
    delBtn.innerHTML = ICONS.delete;
    delBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      deleteTask(task.id);
    });

    li.appendChild(btn);
    li.appendChild(delBtn);
    taskListEl.appendChild(li);
  });

  if (allTasks.length > taskListLimit) {
    viewAllBtn.classList.remove("hidden");
    viewAllBtn.textContent = `View all history (${allTasks.length})`;
  } else {
    viewAllBtn.classList.add("hidden");
  }
}

viewAllBtn.addEventListener("click", () => {
  taskListLimit = allTasks.length;
  renderTaskList();
});

function connectStream(taskId, liveOnly = false) {
  if (socket) {
    socket.close();
  }
  const protocol = location.protocol === "https:" ? "wss:" : "ws:";
  const qs = liveOnly ? "?live=1" : "";
  socket = new WebSocket(`${protocol}//${location.host}/api/tasks/${taskId}/stream${qs}`);

  socket.onmessage = (msg) => {
    let event;
    try {
      event = JSON.parse(msg.data);
    } catch {
      addEvent({ type: "error", message: "Invalid message from server" });
      return;
    }
    if (event.type === "connected") return;
    if (event.type === "confirmation_required") {
      showConfirmationPrompt(event);
      return;
    }
    addEvent(event);
    if (event.type === "task_started") return;
    if (event.type === "final" || event.type === "error") {
      submitBtn.disabled = false;
      loadTasks();
    }
  };

  socket.onerror = () => {
    addEvent({ type: "error", message: "WebSocket connection failed" });
    submitBtn.disabled = false;
  };

  socket.onclose = () => {
    submitBtn.disabled = false;
  };
}

async function loadTasks() {
  let res;
  try {
    res = await fetch("/api/tasks");
  } catch {
    return;
  }
  if (!res.ok) return;
  allTasks = await res.json();
  renderTaskList();
}

async function deleteTask(taskId) {
  const task = allTasks.find((t) => t.id === taskId);
  const msg =
    task?.status === "running"
      ? "This chat is still marked as running (it may be stuck). Stop and delete it?"
      : "Delete this chat from history?";
  if (!confirm(msg)) return;

  const res = await fetch(`/api/tasks/${taskId}`, { method: "DELETE" });
  if (!res.ok) {
    addEvent({ type: "error", message: "Could not delete chat." });
    return;
  }
  if (activeTaskId === taskId) {
    startNewChat();
  }
  await loadTasks();
}

async function loadTaskDetail(taskId) {
  activeTaskId = taskId;
  stepsEl.innerHTML = "";
  renderTaskList();

  let taskRes;
  let stepsRes;
  try {
    [taskRes, stepsRes] = await Promise.all([
      fetch(`/api/tasks/${taskId}`),
      fetch(`/api/tasks/${taskId}/steps`),
    ]);
  } catch {
    addEvent({ type: "error", message: "Failed to load task" });
    return;
  }
  if (!taskRes.ok) {
    addEvent({ type: "error", message: "Task not found" });
    return;
  }
  const task = await taskRes.json();
  const steps = stepsRes.ok ? await stepsRes.json() : [];

  addUserMessage(task.input);

  steps.forEach((step) => {
    if (step.step_type === "user" && step.reasoning) {
      addUserMessage(step.reasoning);
    } else if (step.step_type === "thought" && step.reasoning) {
      addEvent({ type: "thought", content: step.reasoning });
    } else if (step.step_type === "tool_call") {
      addEvent({ type: "tool_call", name: step.tool_name, input: step.tool_input || {} });
    } else if (step.step_type === "observation") {
      addEvent({ type: "tool_result", name: step.tool_name, content: step.tool_output || "" });
    }
  });

  if (task.final_output) {
    if (task.status === "failed") {
      addEvent({ type: "error", message: task.final_output });
    } else {
      addEvent({ type: "final", content: task.final_output });
    }
  }

  if (task.status === "running") {
    connectStream(taskId);
  }
}

async function canContinueTask(taskId) {
  try {
    const res = await fetch(`/api/tasks/${taskId}`);
    if (!res.ok) return false;
    const task = await res.json();
    return task.status === "completed" || task.status === "failed";
  } catch {
    return false;
  }
}

function startNewChat() {
  activeTaskId = null;
  stepsEl.innerHTML = "";
  promptEl.value = "";
  promptEl.focus();
  renderTaskList();
}

newChatBtn.addEventListener("click", startNewChat);

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  const input = promptEl.value.trim();
  if (!input) return;

  submitBtn.disabled = true;
  const isFollowUp = activeTaskId && (await canContinueTask(activeTaskId));

  if (!isFollowUp) {
    stepsEl.innerHTML = "";
  }
  addUserMessage(input);

  const payload = { input, auto_approve: autoApproveEl.checked };
  if (isFollowUp) {
    payload.continue_task_id = activeTaskId;
  }

  const res = await fetch("/api/tasks", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!res.ok) {
    addEvent({ type: "error", message: await res.text() });
    submitBtn.disabled = false;
    return;
  }

  const task = await res.json();
  activeTaskId = task.id;
  promptEl.value = "";
  loadTasks();
  connectStream(task.id, isFollowUp);
});

function showConnectedBanner(message) {
  bannerTextEl.textContent = message;
  bannerEl.classList.remove("hidden", "error");
  manageConnectionEl.classList.remove("hidden");
}

function showErrorBanner(message) {
  bannerTextEl.textContent = message;
  bannerEl.classList.remove("hidden");
  bannerEl.classList.add("error");
  manageConnectionEl.classList.add("hidden");
}

function showBannerFromUrl() {
  const params = new URLSearchParams(location.search);
  if (params.get("google_connected") === "1") {
    localStorage.setItem("google_connected", "1");
    showConnectedBanner("Google account connected. You can use Gmail and Calendar tools.");
    history.replaceState({}, "", "/");
  } else if (params.get("oauth_error")) {
    localStorage.removeItem("google_connected");
    showErrorBanner(decodeURIComponent(params.get("oauth_error")));
    history.replaceState({}, "", "/");
  } else if (localStorage.getItem("google_connected") === "1") {
    showConnectedBanner("Google account connected. You can use Gmail and Calendar tools.");
  }
}

showBannerFromUrl();
loadTasks();
