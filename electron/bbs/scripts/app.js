/*
  简介：本文件实现客户端数据、筛选、排序与渲染逻辑（贴合 JoinQuant 研究交流页）。
  功能：
  - 顶部导航分类、次级排序标签（全部/最新/最热/精华）
  - 关键字搜索
  - 主 Feed：卡片右侧小图/图表、徽章（置顶/精华）、指标、标签
  - 右侧栏：JQData 推广卡片、热门用户、热门话题
  - 列表中插入全宽 JQData 横幅
  - 状态持久化（localStorage）
*/

(function () {
  const qs = (sel, root = document) => root.querySelector(sel);
  const qsa = (sel, root = document) => Array.from(root.querySelectorAll(sel));

  // Mock 数据（16+）
  const posts = [
    { id: 1, title: "量化策略入门：从因子到回测", excerpt: "介绍常见因子、数据预处理与基础回测框架搭建。", category: "文章", tags: ["因子", "回测", "入门"], views: 3240, comments: 18, likes: 96, author: "AlphaChen", createdAt: daysAgo(1), lastCommentAt: hoursAgo(5), featured: true, pinned: true, thumbnail: "/assets/placeholder.svg" },
    { id: 2, title: "如何优化多因子模型的稳健性？", excerpt: "讨论因子正交化、滚动窗口与交叉验证等方法。", category: "文章", tags: ["因子", "优化"], views: 8920, comments: 43, likes: 210, author: "BetaXu", createdAt: daysAgo(3), lastCommentAt: hoursAgo(8), featured: true, pinned: false, thumbnail: "/assets/placeholder.svg" },
    { id: 3, title: "公告：数据服务维护窗口（本周末）", excerpt: "本周末进行数据服务升级，期间部分接口不可用。", category: "公告", tags: ["公告"], views: 15600, comments: 12, likes: 64, author: "官方账号", createdAt: daysAgo(2), lastCommentAt: hoursAgo(18), featured: false, pinned: true, thumbnail: "/assets/placeholder.svg" },
    { id: 4, title: "问答：在哪里获取分钟级交易数据？", excerpt: "新人提问：是否有免费的分钟级数据源？", category: "问答", tags: ["数据", "分钟级"], views: 980, comments: 9, likes: 21, author: "QuantNewbie", createdAt: daysAgo(0), lastCommentAt: hoursAgo(2), featured: false, pinned: false, thumbnail: null },
    { id: 5, title: "多线程回测的踩坑与实践", excerpt: "讲述在回测中引入并行的常见问题与解决方案。", category: "文章", tags: ["回测", "并行"], views: 4320, comments: 27, likes: 120, author: "Threader", createdAt: daysAgo(7), lastCommentAt: hoursAgo(30), featured: false, pinned: false, thumbnail: "/assets/placeholder.svg" },
    { id: 6, title: "公告：新手引导文档更新", excerpt: "补充了策略调试与日志排查章节。", category: "公告", tags: ["公告", "文档"], views: 2640, comments: 6, likes: 44, author: "官方账号", createdAt: daysAgo(5), lastCommentAt: hoursAgo(20), featured: false, pinned: false, thumbnail: null },
    { id: 7, title: "问答：回测结果为何与实盘偏差较大？", excerpt: "讨论滑点、手续费与成交规则对结果的影响。", category: "问答", tags: ["回测", "实盘", "滑点"], views: 2140, comments: 35, likes: 78, author: "Zeta", createdAt: daysAgo(10), lastCommentAt: hoursAgo(3), featured: true, pinned: false, thumbnail: null },
    { id: 8, title: "文章：ETF 轮动策略复盘", excerpt: "基于动量与波动率的组合轮动策略分析。", category: "文章", tags: ["ETF", "轮动", "动量"], views: 6540, comments: 22, likes: 142, author: "Gamma", createdAt: daysAgo(9), lastCommentAt: hoursAgo(13), featured: false, pinned: false, thumbnail: "/assets/placeholder.svg" },
    { id: 9, title: "问答：Pandas 读取大文件的最佳实践？", excerpt: "chunk 加载、dtype 优化与内存管理技巧。", category: "问答", tags: ["Pandas", "性能"], views: 1940, comments: 15, likes: 53, author: "DataCook", createdAt: daysAgo(4), lastCommentAt: hoursAgo(6), featured: false, pinned: false, thumbnail: null },
    { id: 10, title: "文章：因子暴露与组合风险控制", excerpt: "如何衡量与控制因子暴露，减少非预期风险。", category: "文章", tags: ["风险", "因子"], views: 8420, comments: 18, likes: 188, author: "RiskMgr", createdAt: daysAgo(14), lastCommentAt: hoursAgo(48), featured: true, pinned: false, thumbnail: "/assets/placeholder.svg" },
    { id: 11, title: "公告：社区规则更新（文明交流）", excerpt: "新增不友善行为处理机制，请大家互相尊重。", category: "公告", tags: ["公告", "规则"], views: 3120, comments: 5, likes: 33, author: "官方账号", createdAt: daysAgo(11), lastCommentAt: hoursAgo(50), featured: false, pinned: false, thumbnail: null },
    { id: 12, title: "文章：交易成本对策略的影响评估", excerpt: "比较固定与比例费用模型，测算净收益与回撤。", category: "文章", tags: ["交易成本", "回撤"], views: 5220, comments: 19, likes: 118, author: "Delta", createdAt: daysAgo(6), lastCommentAt: hoursAgo(12), featured: false, pinned: false, thumbnail: null },
    { id: 13, title: "问答：如何实现事件驱动的回测框架？", excerpt: "从调度、撮合到日志系统的模块划分。", category: "问答", tags: ["架构", "回测"], views: 2760, comments: 28, likes: 88, author: "Architect", createdAt: daysAgo(8), lastCommentAt: hoursAgo(7), featured: true, pinned: false, thumbnail: "/assets/placeholder.svg" },
    { id: 14, title: "文章：小市值因子再审视", excerpt: "2025 年小市值策略表现与改进方向。", category: "文章", tags: ["小市值", "因子"], views: 9120, comments: 31, likes: 167, author: "SmallCap", createdAt: daysAgo(2), lastCommentAt: hoursAgo(9), featured: true, pinned: false, thumbnail: "/assets/placeholder.svg" },
    { id: 15, title: "问答：如何评估策略过拟合？", excerpt: "交叉验证、样本外测试与稳定性指标。", category: "问答", tags: ["过拟合", "评估"], views: 3840, comments: 24, likes: 97, author: "Validator", createdAt: daysAgo(3), lastCommentAt: hoursAgo(4), featured: false, pinned: false, thumbnail: null },
    { id: 16, title: "文章：机器学习因子挖掘流程", excerpt: "特征工程、模型选择与组合构建实践。", category: "文章", tags: ["机器学习", "因子挖掘"], views: 7380, comments: 26, likes: 155, author: "MLQuant", createdAt: daysAgo(5), lastCommentAt: hoursAgo(11), featured: true, pinned: false, thumbnail: "/assets/placeholder.svg" }
  ].map(p => ({ ...p, score: Math.round(p.likes * 2 + p.comments * 1.5 + p.views / 120) }));

  // 热门用户 Mock
  const hotUsers = [
    { name: "AlphaChen", score: 128, trend: "up" },
    { name: "BetaXu", score: 96, trend: "up" },
    { name: "Gamma", score: 85, trend: "down" },
    { name: "RiskMgr", score: 72, trend: "up" },
    { name: "MLQuant", score: 68, trend: "up" }
  ];

  // 热门话题 Mock
  const hotTopics = [
    { name: "小市值策略", count: 142 },
    { name: "因子挖掘", count: 128 },
    { name: "回测框架", count: 96 },
    { name: "ETF轮动", count: 85 },
    { name: "机器学习", count: 72 }
  ];

  // 状态管理（新增分页）
  const STATE_KEY = "community:list:state";
  const defaultState = { sort: "全部", search: "", page: 1, perPage: 10 };
  let state = loadState() || defaultState;

  // DOM 引用
  const feedEl = qs("#feed");
  const paginationEl = qs("#pagination");
  const searchInput = qs("#searchInput");
  const tabs = qsa(".tab");

  // 初始化 UI
  function initUI() {
    tabs.forEach(t => t.classList.toggle("active", t.dataset.sort === state.sort));
    if (searchInput) searchInput.value = state.search || "";
    // 顶部横幅默认显示（无数据时会被隐藏）
    const topBanner = qs("#topBanner");
    if (topBanner) topBanner.style.display = "flex";
  }

  // 更新分页按钮状态（已整合到分页渲染中）
  function updatePagerState() {
    // 分页状态由 renderPagination 函数统一处理
  }
  // 渲染分页
  function renderPagination() {
    const list = applyFilters();
    const total = list.length;
    if (!total) { paginationEl.innerHTML = ""; return; }
    const totalPages = Math.ceil(total / state.perPage);
    const curr = state.page;
    let html = "";
    // 上一页
    html += `<button class="page-btn" ${curr === 1 ? "disabled" : ""} data-page="${curr - 1}">上一页</button>`;
    // 页码
    const maxButtons = 7; // 最多显示 7 个数字按钮
    let start = Math.max(1, curr - Math.floor(maxButtons / 2));
    let end = Math.min(totalPages, start + maxButtons - 1);
    if (end - start + 1 < maxButtons) start = Math.max(1, end - maxButtons + 1);
    for (let i = start; i <= end; i++) {
      html += `<button class="page-btn ${i === curr ? "active" : ""}" data-page="${i}">${i}</button>`;
    }
    // 下一页
    html += `<button class="page-btn" ${curr === totalPages ? "disabled" : ""} data-page="${curr + 1}">下一页</button>`;
    paginationEl.innerHTML = html;
    // 事件委托
    paginationEl.onclick = e => {
      const btn = e.target.closest("button");
      if (!btn || btn.disabled) return;
      const page = Number(btn.dataset.page);
      if (page === curr) return;
      state.page = page;
      saveState();
      syncStateToURL();
      renderAll();
    };
  }

  // 事件绑定
  function bindEvents() {
    tabs.forEach(t => t.addEventListener("click", () => {
      state.sort = t.dataset.sort;
      state.page = 1; // 切换排序回到第一页
      saveState();
      syncStateToURL();
      renderAll();
    }));
    searchInput.addEventListener("input", () => {
      state.search = searchInput.value.trim();
      state.page = 1; // 搜索回到第一页
      saveState();
      syncStateToURL();
      renderFeed();
    });
    // 分页事件由 renderPagination 函数统一处理（事件委托）
  }

  // 渲染主流程
  function renderAll() {
    initUI();
    renderFeed();
    renderPagination();
    renderSidebars();
  }

  // 过滤与排序
  function applyFilters() {
    let list = [...posts];
    // 排序
    switch (state.sort) {
      case "最新":
        list.sort((a, b) => b.createdAt - a.createdAt);
        break;
      case "最热":
        list.sort((a, b) => b.views - a.views);
        break;
      case "精华":
        list = list.filter(p => p.featured).sort((a, b) => b.score - a.score);
        break;
      default: // 全部
        break;
    }
    // 搜索
    const q = (state.search || "").toLowerCase();
    if (q) {
      list = list.filter(p => (
        p.title.toLowerCase().includes(q) ||
        p.excerpt.toLowerCase().includes(q) ||
        p.author.toLowerCase().includes(q) ||
        (p.tags || []).some(t => t.toLowerCase().includes(q))
      ));
    }
    return list;
  }

  // 渲染 Feed（横幅已移到顶部，不再插入列表）
  function renderFeed() {
    const list = applyFilters();
    if (!list.length) {
      feedEl.innerHTML = `<div class="post-card"><div class="post-main"><div class="post-header"><h3 class="post-title">未找到相关帖子</h3></div><div class="post-meta">试试更换筛选条件或清空搜索关键词。</div></div></div>`;
      return;
    }
    // 分页
    const total = list.length;
    const totalPages = Math.ceil(total / state.perPage);
    const start = (state.page - 1) * state.perPage;
    const pageList = list.slice(start, start + state.perPage);
    const html = pageList.map(renderPostCard).join("");
    feedEl.innerHTML = html;
    // 控制顶部横幅显隐（有数据就显示）
    const topBanner = qs("#topBanner");
    if (topBanner) topBanner.style.display = "flex";
  }

  function renderPostCard(p) {
    const badges = [
      p.pinned ? `<span class="badge pinned">置顶</span>` : "",
      p.featured ? `<span class="badge featured">精</span>` : ""
    ].join("");
    const thumb = p.thumbnail ? `<div class="post-thumb"><img src="${p.thumbnail}" alt="" /></div>` : "";
    const tags = (p.tags || []).slice(0, 3).map(t => `<span class="tag-chip">${escapeHTML(t)}</span>`).join("");
    return `
      <article class="post-card">
        <div class="post-main">
          <div class="post-header">
            <h3 class="post-title"><a class="post-link" href="#/post/${p.id}">${escapeHTML(p.title)}</a></h3>
            ${badges}
          </div>
          <div class="post-meta">${escapeHTML(p.author)} · ${formatTimeAgo(p.createdAt)} · 阅读 ${p.views} · 评论 ${p.comments} · 赞 ${p.likes}</div>
          <div class="post-tags">${tags}</div>
        </div>
        <div class="post-extra">
          <div class="mini-chart" title="趋势"></div>
          ${thumb}
        </div>
      </article>`;
  }

  // 渲染侧边栏
  function renderSidebars() {
    // 热门用户
    const usersHtml = hotUsers.map(u => `
      <li class="user-item">
        <div class="user-avatar"></div>
        <div class="user-info">
          <div class="user-name">${escapeHTML(u.name)}</div>
          <div class="user-stat">影响力 <span class="user-score ${u.trend}">${u.score}</span></div>
        </div>
      </li>`).join("");
    qs("#hotUsers").innerHTML = usersHtml;

    // 热门话题
    const topicsHtml = hotTopics.map(t => `
      <li class="topic-item">
        <span class="topic-name">#${escapeHTML(t.name)}</span>
        <span class="topic-count">${t.count}</span>
      </li>`).join("");
    qs("#hotTopics").innerHTML = topicsHtml;
  }

  // 工具函数
  function daysAgo(n) { return Date.now() - n * 24 * 60 * 60 * 1000; }
  function hoursAgo(n) { return Date.now() - n * 60 * 60 * 1000; }
  function formatTimeAgo(ts) {
    const diff = Date.now() - ts;
    const min = Math.floor(diff / 60000);
    const hour = Math.floor(min / 60);
    const day = Math.floor(hour / 24);
    if (day > 0) return `${day}天前`;
    if (hour > 0) return `${hour}小时前`;
    if (min > 0) return `${min}分钟前`;
    return "刚刚";
  }
  function escapeHTML(str) {
    return String(str).replace(/[&<>"']/g, s => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[s]);
  }
  function loadState() {
    try { const raw = localStorage.getItem(STATE_KEY); return raw ? JSON.parse(raw) : null; } catch { return null; }
  }
  function saveState() {
    try { localStorage.setItem(STATE_KEY, JSON.stringify(state)); } catch {}
  }

  // 启动
  function parseRoute() {
    const h = location.hash.replace(/^#\/?/, "");
    if (!h) return { name: "list", params: {} };
    const parts = h.split("/");
    if (parts[0] === "post" && parts[1]) return { name: "post", params: { id: Number(parts[1]) } };
    return { name: "list", params: {} };
  }

  function renderPostDetailView(id) {
    const p = posts.find(x => x.id === id);
    const detail = qs("#postDetail");
    const feed = qs("#feed");
    if (!p) {
      detail.innerHTML = `<div class="post-detail"><div class="post-detail-meta">未找到该帖子</div><div class="post-detail-actions"><a class="btn" href="#/">返回列表</a></div></div>`;
      detail.classList.add("active");
      feed.style.display = "none";
      return;
    }
    const tags = (p.tags || []).map(t => `<span class="tag-chip">${escapeHTML(t)}</span>`).join("");
    const html = `
      <div class="post-detail">
        <h2 class="post-detail-title">${escapeHTML(p.title)}</h2>
        <div class="post-detail-meta">${escapeHTML(p.author)} · ${formatTimeAgo(p.createdAt)} · 阅读 ${p.views} · 评论 ${p.comments} · 赞 ${p.likes}</div>
        <div class="post-tags" style="margin-top:12px;">${tags}</div>
        <div class="post-detail-body">${escapeHTML(p.excerpt)}</div>
        <div class="post-detail-actions"><a class="btn" href="#/">返回列表</a></div>
      </div>`;
    detail.innerHTML = html;
    detail.classList.add("active");
    feed.style.display = "none";
  }

  function showListView() {
    const detail = qs("#postDetail");
    const feed = qs("#feed");
    detail.classList.remove("active");
    detail.innerHTML = "";
    feed.style.display = "flex";
    renderAll();
  }

  function handleRoute() {
    const r = parseRoute();
    if (r.name === "post") {
      renderPostDetailView(r.params.id);
    } else {
      showListView();
    }
  }

  function initStateFromURL() {
    const sp = new URLSearchParams(location.search);
    const sort = sp.get("sort");
    const q = sp.get("q");
    const page = Number(sp.get("page") || 1);
    if (sort) state.sort = sort;
    if (q) state.search = q;
    if (page > 0) state.page = page;
  }

  function syncStateToURL() {
    const sp = new URLSearchParams();
    sp.set("sort", state.sort);
    if (state.search) sp.set("q", state.search);
    sp.set("page", String(state.page));
    history.replaceState(null, "", `?${sp.toString()}${location.hash}`);
  }

  initStateFromURL();
  initUI();
  bindEvents();
  syncStateToURL();
  window.addEventListener("hashchange", handleRoute);
  handleRoute();
})();
