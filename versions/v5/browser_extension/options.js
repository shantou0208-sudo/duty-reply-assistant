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

const sitesField = document.querySelector("#enabledSites");
const rulesContainer = document.querySelector("#rules");
const repliesContainer = document.querySelector("#replies");
const status = document.querySelector("#status");
const replyHotkeyPrefix = document.querySelector("#replyHotkeyPrefix");

function prefixLabel(prefix) {
  return prefix
    .split("+")
    .map((part) => ({ ctrl: "Ctrl", alt: "Alt", shift: "Shift" }[part] || part))
    .join("+");
}

function addRuleRow(rule = { from: "", to: "" }) {
  const row = document.createElement("div");
  row.className = "rule-row";
  row.innerHTML = `
    <input class="rule-from" type="text" placeholder="原文字">
    <span>→</span>
    <input class="rule-to" type="text" placeholder="替换为">
    <button class="remove-rule ghost" title="删除">×</button>
  `;
  row.querySelector(".rule-from").value = rule.from;
  row.querySelector(".rule-to").value = rule.to;
  row.querySelector(".remove-rule").addEventListener("click", () => row.remove());
  rulesContainer.appendChild(row);
}

function renderReplies(replies, prefix = replyHotkeyPrefix.value) {
  repliesContainer.replaceChildren();
  for (let index = 0; index < 9; index += 1) {
    const row = document.createElement("label");
    row.className = "reply-row";
    const badge = document.createElement("span");
    badge.textContent = `${prefixLabel(prefix)}+${index + 1}`;
    const input = document.createElement("textarea");
    input.rows = 2;
    input.value = replies[index] || "";
    row.append(badge, input);
    repliesContainer.appendChild(row);
  }
}

async function load() {
  const data = await chrome.storage.local.get(DEFAULTS);
  sitesField.value = data.enabledSites.join("\n");
  replyHotkeyPrefix.value = data.replyHotkeyPrefix;
  rulesContainer.replaceChildren();
  data.rules.forEach(addRuleRow);
  renderReplies(data.replies, data.replyHotkeyPrefix);
}

async function save() {
  const enabledSites = [...new Set(
    sitesField.value
      .split(/\r?\n/)
      .map((site) => site.trim().toLowerCase().replace(/^https?:\/\//, "").replace(/\/.*$/, ""))
      .filter(Boolean)
  )];
  const rules = [...rulesContainer.querySelectorAll(".rule-row")]
    .map((row) => ({
      from: row.querySelector(".rule-from").value,
      to: row.querySelector(".rule-to").value
    }))
    .filter((rule) => rule.from);
  const replies = [...repliesContainer.querySelectorAll("textarea")]
    .map((field) => field.value.trim());
  await chrome.storage.local.set({
    enabledSites,
    rules,
    replies,
    replyHotkeyPrefix: replyHotkeyPrefix.value
  });
  status.textContent = "已保存。请刷新工作网页使设置完全生效。";
}

document.querySelector("#addRule").addEventListener("click", () => addRuleRow());
replyHotkeyPrefix.addEventListener("change", () => {
  const replies = [...repliesContainer.querySelectorAll("textarea")].map((field) => field.value);
  renderReplies(replies, replyHotkeyPrefix.value);
});
document.querySelector("#save").addEventListener("click", save);
document.querySelector("#openShortcuts").addEventListener("click", () => {
  const url = navigator.userAgent.includes("Edg/")
    ? "edge://extensions/shortcuts"
    : "chrome://extensions/shortcuts";
  chrome.tabs.create({ url });
});
document.querySelector("#reset").addEventListener("click", async () => {
  if (!confirm("确定恢复默认规则和话术吗？允许的网站将保留。")) return;
  const current = await chrome.storage.local.get(DEFAULTS);
  await chrome.storage.local.set({
    ...DEFAULTS,
    enabledSites: current.enabledSites
  });
  await load();
  status.textContent = "已恢复默认设置。";
});

load();
