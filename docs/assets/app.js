const CATEGORY_LABELS = {
  ai: "【AI】",
  finance: "【金融】",
  tech: "【科技】",
};

const state = {
  manifest: { dates: [] },
  digest: null,
  category: "all",
  selectedDate: null,
  isLatestView: true,
  loading: false,
};

const elements = {
  dateSelect: document.querySelector("#date-select"),
  editionDate: document.querySelector("#edition-date"),
  updatedAt: document.querySelector("#updated-at"),
  digest: document.querySelector("#digest"),
  empty: document.querySelector("#empty-state"),
  banner: document.querySelector("#status-banner"),
  health: document.querySelector("#source-health"),
  filters: [...document.querySelectorAll(".filter")],
};

function shanghaiNow() {
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Shanghai",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
  }).formatToParts(new Date());
  const values = Object.fromEntries(parts.map((part) => [part.type, part.value]));
  return {
    date: `${values.year}-${values.month}-${values.day}`,
    minutes: Number(values.hour) * 60 + Number(values.minute),
  };
}

function formatDateTime(value) {
  if (!value) return "尚未生成";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return new Intl.DateTimeFormat("zh-CN", {
    timeZone: "Asia/Shanghai",
    month: "long",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
  }).format(parsed);
}

async function fetchJson(path) {
  const url = new URL(path, document.baseURI);
  url.searchParams.set("_", String(Date.now()));
  const response = await fetch(url, { cache: "no-store" });
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  return response.json();
}

async function loadManifest() {
  state.manifest = await fetchJson("./data/manifest.json");
  const dates = Array.isArray(state.manifest.dates) ? state.manifest.dates : [];
  elements.dateSelect.replaceChildren();
  if (!dates.length) {
    const option = document.createElement("option");
    option.textContent = "暂无历史";
    option.value = "";
    elements.dateSelect.append(option);
    elements.dateSelect.disabled = true;
    return;
  }
  elements.dateSelect.disabled = false;
  for (const dateValue of dates) {
    const option = document.createElement("option");
    option.value = dateValue;
    option.textContent = dateValue;
    elements.dateSelect.append(option);
  }
}

async function loadDigest(dateValue = null) {
  if (state.loading) return;
  state.loading = true;
  try {
    if (!dateValue || dateValue === state.manifest.latest) {
      state.digest = await fetchJson("./data/latest.json");
      state.selectedDate = state.digest?.date || null;
      state.isLatestView = true;
    } else {
      state.digest = await fetchJson(`./data/${dateValue}.json`);
      state.selectedDate = dateValue;
      state.isLatestView = false;
    }
    elements.dateSelect.value = state.selectedDate || "";
    render();
    showFreshness();
  } catch (error) {
    showBanner(`读取简报失败：${error.message}。稍后会自动重试。`, true);
  } finally {
    state.loading = false;
  }
}

function render() {
  const digest = state.digest;
  elements.digest.replaceChildren();
  if (!digest || !Array.isArray(digest.items) || digest.items.length === 0) {
    elements.empty.hidden = false;
    elements.empty.textContent = "今天还没有可展示的内容。";
    elements.editionDate.textContent = "今日尚未生成";
    elements.updatedAt.textContent = "将在 07:00 前更新";
    elements.health.textContent = "";
    return;
  }
  elements.empty.hidden = true;
  elements.editionDate.textContent = digest.date || "未知日期";
  elements.updatedAt.textContent = `更新于 ${formatDateTime(digest.generated_at)}`;

  const visible = digest.items.filter((item) =>
    state.category === "all" || item.category === state.category
  );
  if (!visible.length) {
    elements.empty.hidden = false;
    elements.empty.textContent = "这个栏目今天没有入选内容。";
  }
  for (const item of visible) {
    elements.digest.append(createCard(item));
  }

  const health = digest.source_health || {};
  elements.health.textContent =
    health.failed > 0
      ? `来源状态：${health.ok || 0} 个正常，${health.failed} 个失败`
      : `来源状态：${health.ok || 0} 个正常`;
}

function createCard(item) {
  const card = document.createElement("article");
  card.className = "card";
  card.dataset.category = item.category;

  const head = document.createElement("div");
  head.className = "card-head";
  const category = document.createElement("span");
  category.className = "category-label";
  category.textContent = CATEGORY_LABELS[item.category] || "【信息】";
  const confidence = document.createElement("span");
  confidence.className = "confidence";
  confidence.textContent = item.confidence || "仍在发展";
  head.append(category, confidence);

  const headline = document.createElement("h2");
  headline.className = "headline";
  headline.textContent = item.headline || "";

  const lines = document.createElement("div");
  lines.className = "card-lines";
  [
    ["发生了什么", item.what_happened],
    ["为什么重要", item.why_it_matters],
    ["可能影响", item.impact],
    ["依据", item.evidence],
  ].forEach(([label, value]) => lines.append(createLine(label, value)));

  const foot = document.createElement("div");
  foot.className = "card-foot";
  const published = document.createElement("span");
  published.textContent = `发布于 ${formatDateTime(item.published_at)}`;
  const links = document.createElement("div");
  links.className = "source-links";
  const sources = Array.isArray(item.sources) ? item.sources : [];
  sources.forEach((source) => {
    const anchor = document.createElement("a");
    anchor.href = source.url;
    anchor.target = "_blank";
    anchor.rel = "noopener noreferrer";
    anchor.textContent = `原文·${source.source_name}`;
    links.append(anchor);
  });
  foot.append(published, links);

  card.append(head, headline, lines, foot);
  return card;
}

function createLine(label, value) {
  const line = document.createElement("p");
  line.className = "card-line";
  const strong = document.createElement("strong");
  strong.textContent = `【${label}】`;
  const span = document.createElement("span");
  span.textContent = value || "暂无";
  line.append(strong, span);
  return line;
}

function showFreshness() {
  if (!state.isLatestView) {
    elements.banner.hidden = true;
    return;
  }
  const now = shanghaiNow();
  const latestDate = state.digest?.date || state.manifest?.latest || null;
  if (latestDate === now.date) {
    elements.banner.hidden = true;
    return;
  }
  if (now.minutes >= 415 && now.minutes <= 435) {
    showBanner("今日内容正在生成，页面会在更新后自动刷新。", false);
  } else if (now.minutes > 435) {
    showBanner(
      `今日内容尚未更新。当前显示 ${latestDate || "空页面"} 的数据，请检查电脑唤醒和网络。`,
      true
    );
  } else {
    showBanner("今天的简报将在 07:00 前更新。", false);
  }
}

function showBanner(message, isError) {
  elements.banner.textContent = message;
  elements.banner.classList.toggle("is-error", isError);
  elements.banner.hidden = false;
}

async function refreshInMorningWindow() {
  const now = shanghaiNow();
  if (now.minutes < 415 || now.minutes > 435) return;
  await loadManifest();
  if (elements.dateSelect.value === state.manifest.latest || !state.selectedDate) {
    await loadDigest(state.manifest.latest);
  }
}

elements.dateSelect.addEventListener("change", async () => {
  await loadDigest(elements.dateSelect.value || null);
});

elements.filters.forEach((button) => {
  button.addEventListener("click", () => {
    state.category = button.dataset.category;
    elements.filters.forEach((item) => item.classList.toggle("is-active", item === button));
    render();
  });
});

document.addEventListener("visibilitychange", () => {
  if (!document.hidden) refreshInMorningWindow();
});

async function initialize() {
  try {
    await loadManifest();
    await loadDigest(state.manifest.latest || null);
  } catch (error) {
    showBanner(`页面初始化失败：${error.message}`, true);
    elements.empty.textContent = "无法读取每日简报。";
  }
  setInterval(refreshInMorningWindow, 30_000);
}

initialize();

