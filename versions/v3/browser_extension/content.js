const DEFAULTS = {
  enabledSites: [],
  autoReplace: true,
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
  editable.focus();
  return document.execCommand("insertText", false, text);
}

document.addEventListener("keydown", (event) => {
  if (!siteIsEnabled() || event.isComposing || !event.altKey || event.ctrlKey || event.metaKey) {
    return;
  }
  const number = Number(event.key);
  if (!Number.isInteger(number) || number < 1 || number > 9) return;
  const reply = settings.replies[number - 1];
  if (!reply || !insertText(event.target, reply)) return;
  event.preventDefault();
  event.stopImmediatePropagation();
}, true);
