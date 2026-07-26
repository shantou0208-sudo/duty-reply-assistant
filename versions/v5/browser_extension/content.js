const DEFAULTS = {
  enabledSites: [],
  autoReplace: true,
  replyHotkeyPrefix: "ctrl+shift",
  rules: [
    { from: "你发一下", to: "麻烦您提供一下" },
    { from: "你截图", to: "麻烦您提供一下相关截图" },
    { from: "你等一下", to: "请您稍等" },
    { from: "你", to: "您" }
  ],
  replies: [
    "老师您好，我们这边先帮您看一下。",
    "老师您好，目前我们这边还在进一步确认，有消息后会及时联系您。",
    "麻烦您提供一下相关截图、报错信息和作业编号，我们这边进一步排查。",
    "老师您好，目前任务还在排队，请您先耐心等待，我们也会继续关注。",
    "老师您好，该问题已经处理完成，麻烦您重新尝试一下。",
    "老师您好，这个问题需要进一步确认，我们已转交相关老师处理。",
    "好的老师，如果后续还有问题，您可以随时联系我们。",
    "",
    ""
  ]
};

let settings = structuredClone(DEFAULTS);
let isComposing = false;
let internalChange = false;

function normalizeHost(value) {
  return String(value || "")
    .trim()
    .toLowerCase()
    .replace(/^https?:\/\//, "")
    .replace(/\/.*$/, "")
    .replace(/^\*\./, "");
}

function siteIsEnabled() {
  const host = location.hostname.toLowerCase();
  return settings.enabledSites.some((item) => {
    const allowed = normalizeHost(item);
    return allowed && (host === allowed || host.endsWith(`.${allowed}`));
  });
}

async function loadSettings() {
  const saved = await chrome.storage.local.get(DEFAULTS);
  settings = { ...DEFAULTS, ...saved };
}

chrome.storage.onChanged.addListener((changes, area) => {
  if (area !== "local") return;
  for (const [key, change] of Object.entries(changes)) {
    settings[key] = change.newValue;
  }
});

loadSettings();

function isEditable(element) {
  if (!element || !(element instanceof Element)) return false;
  if (element.closest("input[type='password'], pre, code, [data-duty-assistant-ignore]")) {
    return false;
  }
  if (element instanceof HTMLTextAreaElement) return !element.readOnly && !element.disabled;
  if (element instanceof HTMLInputElement) {
    return ["text", "search", "email", "url", "tel", ""].includes(element.type) &&
      !element.readOnly &&
      !element.disabled;
  }
  return Boolean(element.isContentEditable || element.closest("[contenteditable='true']"));
}

function editableFromEvent(event) {
  const path = typeof event.composedPath === "function" ? event.composedPath() : [];
  for (const candidate of path) {
    if (candidate instanceof Element && isEditable(candidate)) return candidate;
  }
  if (isEditable(event.target)) return event.target;
  if (isEditable(document.activeElement)) return document.activeElement;
  return null;
}

function applyRules(text) {
  let output = text;
  const ordered = [...settings.rules]
    .filter((rule) => rule && rule.from)
    .sort((a, b) => b.from.length - a.from.length);
  for (const rule of ordered) {
    output = output.split(rule.from).join(rule.to ?? "");
  }
  return output;
}

function replaceInTextControl(element) {
  const oldValue = element.value;
  const newValue = applyRules(oldValue);
  if (newValue === oldValue) return;

  const start = element.selectionStart ?? oldValue.length;
  const end = element.selectionEnd ?? start;
  const newStart = applyRules(oldValue.slice(0, start)).length;
  const newEnd = applyRules(oldValue.slice(0, end)).length;

  internalChange = true;
  const descriptor = Object.getOwnPropertyDescriptor(
    Object.getPrototypeOf(element),
    "value"
  );
  if (descriptor?.set) descriptor.set.call(element, newValue);
  else element.value = newValue;
  element.setSelectionRange(newStart, newEnd);
  element.dispatchEvent(new InputEvent("input", {
    bubbles: true,
    inputType: "insertReplacementText",
    data: null
  }));
  internalChange = false;
}

function replaceInContentEditable(element) {
  const root = element.closest("[contenteditable='true']") || element;
  const selection = window.getSelection();
  if (!selection || selection.rangeCount === 0 || !root.contains(selection.anchorNode)) return;

  let node = selection.anchorNode;
  let offset = selection.anchorOffset;
  if (node?.nodeType !== Node.TEXT_NODE) {
    const range = selection.getRangeAt(0);
    node = range.startContainer;
    offset = range.startOffset;
  }
  if (!node || node.nodeType !== Node.TEXT_NODE) return;

  const oldText = node.nodeValue || "";
  const newText = applyRules(oldText);
  if (newText === oldText) return;
  const newOffset = applyRules(oldText.slice(0, offset)).length;

  internalChange = true;
  node.nodeValue = newText;
  const range = document.createRange();
  range.setStart(node, Math.min(newOffset, newText.length));
  range.collapse(true);
  selection.removeAllRanges();
  selection.addRange(range);
  root.dispatchEvent(new InputEvent("input", {
    bubbles: true,
    inputType: "insertReplacementText",
    data: null
  }));
  internalChange = false;
}

function processTarget(target) {
  if (!settings.autoReplace || !siteIsEnabled() || internalChange || !isEditable(target)) {
    return;
  }
  if (target instanceof HTMLInputElement || target instanceof HTMLTextAreaElement) {
    replaceInTextControl(target);
  } else {
    replaceInContentEditable(target);
  }
}

document.addEventListener("compositionstart", () => {
  isComposing = true;
}, true);

document.addEventListener("compositionend", (event) => {
  isComposing = false;
  queueMicrotask(() => processTarget(event.target));
}, true);

document.addEventListener("input", (event) => {
  if (!isComposing) processTarget(event.target);
}, true);

function insertText(target, text) {
  if (!text || !isEditable(target)) return false;
  if (target instanceof HTMLInputElement || target instanceof HTMLTextAreaElement) {
    const start = target.selectionStart ?? target.value.length;
    const end = target.selectionEnd ?? start;
    target.setRangeText(text, start, end, "end");
    target.dispatchEvent(new InputEvent("input", {
      bubbles: true,
      inputType: "insertText",
      data: text
    }));
    return true;
  }
  const editable = target.closest("[contenteditable='true']") || target;
  const selection = window.getSelection();
  if (selection?.rangeCount && editable.contains(selection.anchorNode)) {
    const inserted = document.execCommand("insertText", false, text);
    if (inserted) return true;
    const range = selection.getRangeAt(0);
    range.deleteContents();
    const node = document.createTextNode(text);
    range.insertNode(node);
    range.setStartAfter(node);
    range.collapse(true);
    selection.removeAllRanges();
    selection.addRange(range);
    editable.dispatchEvent(new InputEvent("input", {
      bubbles: true,
      inputType: "insertText",
      data: text
    }));
    return true;
  }
  return false;
}

function replyModifiersMatch(event) {
  const expected = new Set(settings.replyHotkeyPrefix.split("+"));
  return (
    event.ctrlKey === expected.has("ctrl") &&
    event.altKey === expected.has("alt") &&
    event.shiftKey === expected.has("shift") &&
    !event.metaKey
  );
}

window.addEventListener("keydown", (event) => {
  if (
    !siteIsEnabled() ||
    event.isComposing ||
    !replyModifiersMatch(event)
  ) {
    return;
  }
  const match = /^Digit([1-9])$/.exec(event.code);
  if (!match) return;
  const number = Number(match[1]);
  const reply = settings.replies[number - 1];
  const target = editableFromEvent(event);
  if (!reply || !target || !insertText(target, reply)) return;
  event.preventDefault();
  event.stopImmediatePropagation();
}, true);

let commandPaletteHost = null;
let commandResults = [];
let activeCommandIndex = 0;

function commandScore(item, query) {
  const normalized = query.trim().toLowerCase();
  if (!normalized) return 1;
  const fields = {
    title: item.title.toLowerCase(),
    command: item.command.toLowerCase(),
    category: item.category.toLowerCase(),
    rest: `${item.description} ${item.keywords}`.toLowerCase()
  };
  let score = 0;
  if (fields.command === normalized) score += 100;
  if (fields.title === normalized) score += 80;
  if (fields.title.includes(normalized)) score += 45;
  if (fields.command.includes(normalized)) score += 35;
  if (fields.category.includes(normalized)) score += 20;
  if (fields.rest.includes(normalized)) score += 15;
  for (const token of normalized.split(/\s+/).filter(Boolean)) {
    if (fields.title.includes(token)) score += 12;
    if (fields.command.includes(token)) score += 10;
    if (fields.rest.includes(token)) score += 5;
  }
  return score;
}

function copyCommand(command, statusElement) {
  navigator.clipboard.writeText(command).then(() => {
    statusElement.textContent = `已复制：${command}`;
  }).catch(() => {
    statusElement.textContent = "复制失败，请手动选中命令复制。";
  });
}

function openCommandPalette() {
  if (commandPaletteHost) {
    commandPaletteHost.shadowRoot.querySelector("input").focus();
    return;
  }

  commandPaletteHost = document.createElement("div");
  commandPaletteHost.style.cssText =
    "position:fixed;inset:0;z-index:2147483647;display:block;";
  document.documentElement.appendChild(commandPaletteHost);
  const shadow = commandPaletteHost.attachShadow({ mode: "open" });
  shadow.innerHTML = `
    <style>
      *{box-sizing:border-box}
      .backdrop{position:fixed;inset:0;background:rgba(45,41,39,.38);display:flex;
        justify-content:center;align-items:flex-start;padding-top:min(14vh,120px);
        font-family:"Microsoft YaHei UI","PingFang SC",sans-serif;color:#514b49}
      .palette{width:min(760px,calc(100vw - 32px));max-height:72vh;background:#f8f3ed;
        border:1px solid #d9cec5;border-radius:18px;box-shadow:0 24px 70px rgba(40,35,33,.22);
        overflow:hidden}
      .head{padding:20px 22px 14px;border-bottom:1px solid #d9cec5}
      .eyebrow{font-size:11px;letter-spacing:1.5px;color:#71806e;font-weight:700}
      h2{font-size:20px;margin:5px 0 13px;color:#936d72}
      input{width:100%;border:1px solid #cdbfB6;border-radius:11px;background:#fffdfa;
        color:#514b49;font:15px inherit;padding:12px 14px;outline:none}
      input:focus{border-color:#c89fa3;box-shadow:0 0 0 3px rgba(200,159,163,.2)}
      .results{max-height:48vh;overflow:auto;padding:8px}
      .item{display:grid;grid-template-columns:90px 1fr auto;gap:12px;align-items:center;
        padding:12px 14px;border-radius:11px;cursor:pointer}
      .item:hover,.item.active{background:#eadbd9}
      .tag{font-size:12px;color:#71806e;background:#dfe6dc;border-radius:999px;
        padding:5px 9px;text-align:center}
      .title{font-weight:700;margin-bottom:5px}
      code{display:block;color:#6d5257;font:13px Consolas,monospace;white-space:normal}
      .desc{color:#817976;font-size:12px;margin-top:4px}
      button{border:0;border-radius:9px;background:#a9b7a5;color:white;padding:8px 11px;
        cursor:pointer;font:12px inherit}
      .foot{display:flex;justify-content:space-between;gap:12px;padding:11px 18px;
        border-top:1px solid #d9cec5;color:#817976;font-size:12px}
      .empty{padding:32px;text-align:center;color:#817976}
    </style>
    <div class="backdrop">
      <section class="palette" role="dialog" aria-modal="true" aria-label="Linux 命令搜索">
        <div class="head">
          <span class="eyebrow">LINUX · SLURM · GPU</span>
          <h2>命令知识库</h2>
          <input type="search" placeholder="输入中文或英文，例如：怎么看节点、显存、tail、squeue">
        </div>
        <div class="results"></div>
        <div class="foot"><span class="status">↑↓ 选择　Enter 复制　Esc 关闭</span><span>Ctrl+Shift+K</span></div>
      </section>
    </div>
  `;

  const input = shadow.querySelector("input");
  const results = shadow.querySelector(".results");
  const status = shadow.querySelector(".status");

  function render() {
    const query = input.value;
    commandResults = (globalThis.DUTY_LINUX_COMMANDS || [])
      .map((item) => ({ item, score: commandScore(item, query) }))
      .filter((entry) => entry.score > 0)
      .sort((a, b) => b.score - a.score || a.item.title.localeCompare(b.item.title))
      .slice(0, 10)
      .map((entry) => entry.item);
    activeCommandIndex = Math.min(activeCommandIndex, Math.max(0, commandResults.length - 1));
    results.replaceChildren();
    if (!commandResults.length) {
      const empty = document.createElement("div");
      empty.className = "empty";
      empty.textContent = "没有找到匹配命令，可以换一个关键词。";
      results.appendChild(empty);
      return;
    }
    commandResults.forEach((item, index) => {
      const row = document.createElement("div");
      row.className = `item${index === activeCommandIndex ? " active" : ""}`;
      row.innerHTML = `
        <span class="tag"></span>
        <div><div class="title"></div><code></code><div class="desc"></div></div>
        <button>复制</button>
      `;
      row.querySelector(".tag").textContent = item.category;
      row.querySelector(".title").textContent = item.title;
      row.querySelector("code").textContent = item.command;
      row.querySelector(".desc").textContent = item.description;
      row.addEventListener("mouseenter", () => {
        activeCommandIndex = index;
        results.querySelectorAll(".item").forEach((element, itemIndex) => {
          element.classList.toggle("active", itemIndex === activeCommandIndex);
        });
      });
      row.addEventListener("click", () => copyCommand(item.command, status));
      results.appendChild(row);
    });
  }

  function close() {
    commandPaletteHost?.remove();
    commandPaletteHost = null;
  }

  input.addEventListener("input", () => {
    activeCommandIndex = 0;
    render();
  });
  input.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      event.preventDefault();
      close();
    } else if (event.key === "ArrowDown") {
      event.preventDefault();
      activeCommandIndex = Math.min(activeCommandIndex + 1, commandResults.length - 1);
      render();
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      activeCommandIndex = Math.max(activeCommandIndex - 1, 0);
      render();
    } else if (event.key === "Enter" && commandResults[activeCommandIndex]) {
      event.preventDefault();
      copyCommand(commandResults[activeCommandIndex].command, status);
    }
  });
  shadow.querySelector(".backdrop").addEventListener("mousedown", (event) => {
    if (event.target.classList.contains("backdrop")) close();
  });
  render();
  input.focus();
}

chrome.runtime.onMessage.addListener((message) => {
  if (message?.type === "OPEN_LINUX_SEARCH") openCommandPalette();
});
