chrome.commands.onCommand.addListener(async (command) => {
  if (command !== "open-linux-search") return;
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab?.id) return;
  try {
    await chrome.tabs.sendMessage(tab.id, { type: "OPEN_LINUX_SEARCH" });
  } catch {
    // 浏览器内部页面、尚未刷新或未授权的页面没有内容脚本。
  }
});
