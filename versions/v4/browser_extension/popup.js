const DEFAULTS = { enabledSites: [], autoReplace: true };
const siteLabel = document.querySelector("#siteLabel");
const siteEnabled = document.querySelector("#siteEnabled");
const autoReplace = document.querySelector("#autoReplace");
const status = document.querySelector("#status");
let currentHost = "";

function normalizeHost(value) {
  return String(value || "").trim().toLowerCase().replace(/^\*\./, "");
}

function hostMatches(host, allowed) {
  const clean = normalizeHost(allowed);
  return clean && (host === clean || host.endsWith(`.${clean}`));
}

async function init() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  try {
    currentHost = new URL(tab.url).hostname.toLowerCase();
  } catch {
    currentHost = "";
  }
  const data = await chrome.storage.local.get(DEFAULTS);
  siteLabel.textContent = currentHost || "此页面不支持扩展";
  siteEnabled.checked = data.enabledSites.some((site) => hostMatches(currentHost, site));
  siteEnabled.disabled = !currentHost;
  autoReplace.checked = data.autoReplace;
}

siteEnabled.addEventListener("change", async () => {
  const data = await chrome.storage.local.get(DEFAULTS);
  let sites = data.enabledSites.map(normalizeHost).filter(Boolean);
  if (siteEnabled.checked) {
    if (!sites.includes(currentHost)) sites.push(currentHost);
  } else {
    sites = sites.filter((site) => !hostMatches(currentHost, site));
  }
  await chrome.storage.local.set({ enabledSites: sites });
  status.textContent = siteEnabled.checked ? "已启用，请刷新工作网页。" : "已对此网站停用。";
});

autoReplace.addEventListener("change", async () => {
  await chrome.storage.local.set({ autoReplace: autoReplace.checked });
  status.textContent = autoReplace.checked ? "自动替换已开启。" : "自动替换已暂停。";
});

document.querySelector("#openOptions").addEventListener("click", () => {
  chrome.runtime.openOptionsPage();
});

document.querySelector("#openLinux").addEventListener("click", async () => {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab?.id) return;
  try {
    await chrome.tabs.sendMessage(tab.id, { type: "OPEN_LINUX_SEARCH" });
    window.close();
  } catch {
    status.textContent = "此页面不支持命令面板，请在普通网页中使用。";
  }
});

init();
