// ===== Festival Planner Module (separate file) =====
// All variables use FP_ prefix to avoid conflicts

// Config
var FP_CONFIG = {
  logisticsModes: {
    air:   { leadTime: 16, production: 3,  transit: 13, label: "空运13天" },
    truck: { leadTime: 33, production: 3, transit: 30, label: "卡航30天" },
    sea:   { leadTime: 63, production: 3, transit: 60, label: "海运60天" }
  },
  arrivalBuffer: 14,
  defaultLogistics: "truck",
  milestones: [
    { id: "selection",  daysBeforeSource: "leadTime+14", name: "选品+下单",    actions: "定SKU；同时下空运首批50件+大货订单（出厂{production}天）" },
    { id: "airArrival", daysBeforeSource: "leadTime+1",  name: "空运首批到仓", actions: "空运13天到仓，开始测款观察" },
    { id: "truckShip",  daysBeforeSource: "transit+14",  name: "大货发运",      actions: "大货出厂发UK（{modeLabel}约{transit}天到FBA）" },
    { id: "arrival",    daysBefore: 14,                  name: "大货到仓",      actions: "到FBA仓库→入仓2天→缓冲12天后上架销售" },
    { id: "festival",   daysBefore: 0,                   name: "节日销售",      actions: "广告加投，促销启动" }
  ],
  urgencyThresholds: { urgent: 0, week: 7, month: 30, plan: Infinity },
  categories: {
    decor:   { label: "🎃装饰", color: "#fb923c" },
    gift:    { label: "🎁礼品", color: "#ec4899" },
    apparel: { label: "👕服饰", color: "#8b5cf6" },
    home:    { label: "🏠家居", color: "#14b8a6" }
  },
  months: [
    { num: 1, label: "1月" }, { num: 2, label: "2月" }, { num: 3, label: "3月" },
    { num: 4, label: "4月" }, { num: 5, label: "5月" }, { num: 6, label: "6月" },
    { num: 7, label: "7月" }, { num: 8, label: "8月" }, { num: 9, label: "9月" },
    { num: 10, label: "10月" }, { num: 11, label: "11月" }, { num: 12, label: "12月" }
  ],
  storageKey: "uk_festival_planner_v1"
};

// State
var FP_State = {
  data: null,
  load: function() {
    var raw = localStorage.getItem(FP_CONFIG.storageKey);
    if (raw) { try { this.data = JSON.parse(raw); } catch(e) { this.init(); } }
    else { this.init(); }
    return this.data;
  },
  init: function() {
    this.data = { version: "1.0", lastUpdated: new Date().toISOString(), festivals: {} };
    this.save();
  },
  save: function() {
    this.data.lastUpdated = new Date().toISOString();
    try { localStorage.setItem(FP_CONFIG.storageKey, JSON.stringify(this.data)); }
    catch(e) { console.warn("Save failed", e); }
  },
  getFestival: function(id) {
    if (!this.data.festivals[id]) {
      this.data.festivals[id] = {
        status: "none", logistics: FP_CONFIG.defaultLogistics,
        milestones: { selection: false, airArrival: false, truckShip: false, arrival: false, festival: false },
        notes: "", selectedSkus: []
      };
    }
    return this.data.festivals[id];
  },
  updateFestival: function(id, updates) {
    Object.assign(this.getFestival(id), updates);
    this.save();
  },
  toggleMilestone: function(id, mid) {
    var f = this.getFestival(id);
    f.milestones[mid] = !f.milestones[mid];
    this.save();
  },
  toggleSku: function(id, sku) {
    var f = this.getFestival(id);
    var i = f.selectedSkus.indexOf(sku);
    if (i >= 0) f.selectedSkus.splice(i, 1);
    else f.selectedSkus.push(sku);
    this.save();
  },
  export: function() { return JSON.stringify(this.data, null, 2); },
  import: function(str) {
    var p = JSON.parse(str);
    if (!p.version || !p.festivals) throw new Error("Invalid format");
    this.data = p; this.save();
  },
  reset: function() { localStorage.removeItem(FP_CONFIG.storageKey); this.init(); }
};

// Filter
var FP_Filter = {
  category: "", month: "", urgency: "", status: "", search: "", statCardUrgency: ""
};

// Utils
var FP_Utils = {
  parseDate: function(str) {
    var parts = str.split("-").map(Number);
    return new Date(parts[0], parts[1] - 1, parts[2]);
  },
  today: function() { var d = new Date(); d.setHours(0,0,0,0); return d; },
  diffDays: function(a, b) { return Math.round((a - b) / 86400000); },
  fmtMD: function(date) { return (date.getMonth() + 1) + "/" + date.getDate(); },
  fmtYMD: function(date) {
    return date.getFullYear() + "-" + String(date.getMonth() + 1).padStart(2,"0") + "-" + String(date.getDate()).padStart(2,"0");
  },
  getSelectionDeadline: function(festivalDate, logistics) {
    var mode = FP_CONFIG.logisticsModes[logistics];
    var d = new Date(this.parseDate(festivalDate));
    d.setDate(d.getDate() - (mode.leadTime + 14));
    return d;
  },
  getMilestoneDates: function(festival) {
    var logistics = FP_State.getFestival(festival.id).logistics;
    var mode = FP_CONFIG.logisticsModes[logistics];
    return FP_CONFIG.milestones.map(function(ms) {
      var daysBefore;
      if (ms.daysBeforeSource) {
        var expr = ms.daysBeforeSource;
        if (expr.indexOf("+") >= 0) {
          var parts = expr.split("+");
          daysBefore = mode[parts[0]] + parseInt(parts[1]);
        } else {
          daysBefore = mode[expr];
        }
      } else {
        daysBefore = ms.daysBefore;
      }
      var d = new Date(FP_Utils.parseDate(festival.date));
      d.setDate(d.getDate() - daysBefore);
      var actions = (ms.actions || "").replace(/\{modeLabel\}/g, mode.label)
        .replace(/\{transit\}/g, mode.transit).replace(/\{leadTime\}/g, mode.leadTime)
        .replace(/\{production\}/g, mode.production);
      return { id: ms.id, name: ms.name, actions: actions, date: d, dateStr: FP_Utils.fmtMD(d) };
    });
  },
  getUrgency: function(festival) {
    var festState = FP_State.getFestival(festival.id);
    var fDate = this.parseDate(festival.date);
    var today = this.today();
    if (fDate < today) return "past";
    var deadline = this.getSelectionDeadline(festival.date, festState.logistics);
    var days = this.diffDays(deadline, today);
    if (days < 0) {
      if (festState.milestones.selection) return "plan";
      return "urgent";
    } else if (days <= FP_CONFIG.urgencyThresholds.week) return "week";
    else if (days <= FP_CONFIG.urgencyThresholds.month) return "month";
    return "plan";
  },
  urgencyLabel: function(u) {
    return ({ urgent:"🔴紧急", week:"🟠本周启动", month:"🟡本月备货", plan:"🟢规划中", past:"⚫已过" })[u] || u;
  },
  escape: function(str) {
    var div = document.createElement("div");
    div.textContent = str || "";
    return div.innerHTML;
  },
  debounce: function(fn, ms) {
    var t;
    return function() { var args = arguments; clearTimeout(t); t = setTimeout(function() { fn.apply(null, args); }, ms); };
  }
};

// Render
var FP_expandedCards = {};
var FP_Render = {
  monthNav: function() {
    var el = document.getElementById("monthNav");
    if (el) el.innerHTML = FP_CONFIG.months.map(function(m) {
      return '<a href="#month-' + m.num + '" style="padding:6px 14px;border-radius:8px;text-decoration:none;color:var(--muted);font-size:13px;font-weight:500;transition:all .15s;border:1px solid transparent">' + m.label + '</a>';
    }).join("");
  },

  dashboard: function() {
    var stats = { urgent: 0, week: 0, month: 0, plan: 0, past: 0 };
    FESTIVALS.forEach(function(f) { stats[FP_Utils.getUrgency(f)]++; });

    var upcoming = FESTIVALS
      .filter(function(f) { return FP_Utils.getUrgency(f) !== "past"; })
      .map(function(f) { return { fest: f, deadline: FP_Utils.getSelectionDeadline(f.date, FP_State.getFestival(f.id).logistics) }; })
      .sort(function(a, b) { return a.deadline - b.deadline; })[0];

    var cd = document.getElementById("countdown");
    if (cd && upcoming) {
      var days = FP_Utils.diffDays(upcoming.deadline, FP_Utils.today());
      var u = FP_Utils.getUrgency(upcoming.fest);
      var daysText = days > 0 ? '剩余' + days + '天' : days === 0 ? '今天！' : '已超' + Math.abs(days) + '天';
      cd.innerHTML = '今日 <strong>' + FP_Utils.fmtYMD(FP_Utils.today()) + '</strong> · 最近备货节点：<strong>' + upcoming.fest.icon + ' ' + upcoming.fest.name + '</strong>（' + upcoming.fest.date + '）· 选品截止 <strong>' + FP_Utils.fmtYMD(upcoming.deadline) + '</strong> · <span style="padding:2px 8px;border-radius:6px;font-size:12px;font-weight:700;background:var(--' + (u === 'urgent' ? 'red' : u === 'week' ? 'orange' : u === 'month' ? 'yellow' : 'green') + ');color:' + (u === 'month' ? 'var(--text)' : '#fff') + '">' + FP_Utils.urgencyLabel(u) + ' ' + daysText + '</span>';
    }

    var cards = [
      { key:"urgent", num:stats.urgent, label:"🔴 紧急（已过截止）", color:"var(--red)" },
      { key:"week",   num:stats.week,   label:"🟠 本周必须启动", color:"var(--orange)" },
      { key:"month",  num:stats.month,  label:"🟡 本月需备货", color:"#eab308" },
      { key:"plan",   num:stats.plan,   label:"🟢 规划观察中", color:"var(--green)" }
    ];
    var sc = document.getElementById("statCards");
    if (sc) sc.innerHTML = cards.map(function(c) {
      var isActive = FP_Filter.statCardUrgency === c.key;
      return '<div class="fp-stat-card' + (isActive ? ' active' : '') + '" style="border-left-color:' + c.color + '" onclick="FP_Filter.statCardUrgency=\'' + (isActive ? '' : c.key) + '\';FP_Filter.search=\'\';document.getElementById(\'filterSearch\').value=\'\';document.getElementById(\'filterUrgency\').value=\'' + (isActive ? '' : c.key) + '\';FP_Render.dashboard();FP_Render.main()"><div style="font-size:28px;font-weight:700;color:' + c.color + '">' + c.num + '</div><div style="font-size:12px;color:var(--muted);margin-top:2px">' + c.label + '</div></div>';
    }).join("");
    // Freshness indicator
    var freshnessEl = document.getElementById("fpFreshness");
    if (freshnessEl && FP_State.data && FP_State.data.lastUpdated) {
      var lastDate = new Date(FP_State.data.lastUpdated);
      var daysSince = FP_Utils.diffDays(FP_Utils.today(), lastDate);
      var dotCls = daysSince <= 3 ? 'green' : daysSince <= 7 ? 'yellow' : 'orange';
      var msg = daysSince <= 0 ? '数据刚刚更新' : daysSince <= 3 ? '数据最新（' + daysSince + '天前更新）' : daysSince <= 7 ? '数据已' + daysSince + '天未更新' : '数据较旧（' + daysSince + '天前），建议同步最新进度';
      freshnessEl.innerHTML = '<span class="dot ' + dotCls + '"></span><span>' + msg + '</span>';
    }
    // Update tab counter
    var fpCnt = document.getElementById("fpCnt");
    if (fpCnt) fpCnt.textContent = FESTIVALS.length;
  },

  main: function() {
    var filtered = FESTIVALS.filter(function(f) {
      var festState = FP_State.getFestival(f.id);
      var urgency = FP_Utils.getUrgency(f);
      if (FP_Filter.category && !f.products.some(function(p) { return p.category === FP_Filter.category; })) return false;
      if (FP_Filter.month && f.month !== parseInt(FP_Filter.month)) return false;
      var effU = FP_Filter.statCardUrgency || FP_Filter.urgency;
      if (effU && urgency !== effU) return false;
      if (FP_Filter.status && festState.status !== FP_Filter.status) return false;
      if (FP_Filter.search) {
        var q = FP_Filter.search.toLowerCase();
        var hay = (f.name + f.nameEn + f.icon +
          f.products.map(function(p) { return p.sku + p.skuEn + p.keywords.join(""); }).join("")).toLowerCase();
        if (hay.indexOf(q) < 0) return false;
      }
      return true;
    });

    var mainEl = document.getElementById("main");
    if (!mainEl) return;
    if (filtered.length === 0) {
      mainEl.innerHTML = '<div class="fp-empty"><div class="icon">🔍</div><p>没有匹配的节日，试试调整筛选条件</p><button onclick="FP_Interact.resetFilter()">重置筛选</button></div>';
      return;
    }

    var byMonth = {};
    filtered.forEach(function(f) { (byMonth[f.month] = byMonth[f.month] || []).push(f); });

    var html = "";
    FP_CONFIG.months.forEach(function(m) {
      if (!byMonth[m.num]) return;
      var fests = byMonth[m.num].sort(function(a, b) { return new Date(a.date) - new Date(b.date); });
      html += '<div class="month-section" id="month-' + m.num + '"><h2>' + m.label + ' <span class="cnt">(' + fests.length + ')</span></h2><div style="display:flex;flex-direction:column;gap:16px">';
      fests.forEach(function(f) { html += FP_Render.festivalCard(f); });
      html += '</div></div>';
    });
    mainEl.innerHTML = html;
  },

  festivalCard: function(f) {
    var festState = FP_State.getFestival(f.id);
    var urgency = FP_Utils.getUrgency(f);
    var deadline = FP_Utils.getSelectionDeadline(f.date, festState.logistics);
    var days = FP_Utils.diffDays(deadline, FP_Utils.today());

    var urgColors = { urgent:"var(--red)", week:"var(--orange)", month:"#eab308", plan:"var(--green)", past:"#8e8e93" };
    var impBg = { S:"#FF2D5515", A:"#FF950015", B:"#007AFF15" };
    var impFg = { S:"var(--red)", A:"var(--orange)", B:"var(--blue)" };
    var statusOptions = [
      { v:"none", l:"未启动", c:"#8e8e93" },
      { v:"selection", l:"选品中", c:"#007AFF" },
      { v:"ordered", l:"已下单", c:"#FF9500" },
      { v:"arrived", l:"已到仓", c:"#AF52DE" },
      { v:"listed", l:"已上架", c:"#34C759" }
    ];
    var stOpt = statusOptions.find(function(o) { return o.v === festState.status; }) || statusOptions[0];
    var isExpanded = FP_expandedCards[f.id];

    var html = '<div class="festival-card' + (isExpanded ? ' expanded' : '') + '" id="card-' + f.id + '" data-urgency="' + urgency + '">';
    html += '<div class="card-header" onclick="FP_Interact.toggleCard(\'' + f.id + '\')">';
    html += '<span style="font-size:32px;flex-shrink:0">' + f.icon + '</span>';
    html += '<div style="flex:1;min-width:0">';
    html += '<div style="font-size:17px;font-weight:700;color:var(--text)">' + FP_Utils.escape(f.name) + ' <span style="font-size:12px;color:var(--muted);font-weight:400">' + FP_Utils.escape(f.nameEn) + '</span></div>';
    html += '<div style="display:flex;gap:8px;margin-top:6px;flex-wrap:wrap;align-items:center">';
    html += '<span style="padding:2px 8px;border-radius:6px;font-size:11px;font-weight:700;background:' + impBg[f.importance] + ';color:' + impFg[f.importance] + '">' + f.importance + '</span>';
    html += '<span style="font-size:12px;color:var(--muted)">' + f.date + '</span>';
    html += '<span style="font-size:12px;color:var(--muted)">' + f.products.length + ' SKUs</span>';
    html += '<span style="padding:2px 8px;border-radius:6px;font-size:11px;font-weight:600;background:' + stOpt.c + '22;color:' + stOpt.c + '">' + stOpt.l + '</span>';
    html += '</div></div>';
    html += '<span style="padding:4px 12px;border-radius:10px;font-size:12px;font-weight:700;background:' + urgColors[urgency] + ';color:#fff;white-space:nowrap;flex-shrink:0">' + FP_Utils.urgencyLabel(urgency) + '</span>';
    html += '<span style="font-size:16px;color:var(--muted);flex-shrink:0;transition:transform .2s">' + (isExpanded ? '&#9660;' : '&#9654;') + '</span>';
    html += '</div>';

    // Detail
    html += '<div class="card-body">';

    // Deadline
    html += '<div style="margin-bottom:12px;padding:10px;background:#f8f8fa;border-radius:8px;font-size:13px">';
    html += '<strong>选品截止日：</strong> ' + FP_Utils.fmtYMD(deadline) + ' (' + (days > 0 ? '剩余' + days + '天' : days === 0 ? '今天！' : '已超' + Math.abs(days) + '天') + ')';
    html += '</div>';

    // Logistics toggle
    html += '<div style="display:flex;gap:4px;margin-bottom:12px;align-items:center">';
    html += '<label style="font-size:12px;color:#6e6e73;margin-right:4px">物流方式：</label>';
    ["sea","truck","air"].forEach(function(mode) {
      var active = festState.logistics === mode;
      var label = FP_CONFIG.logisticsModes[mode].label;
      html += '<button onclick="FP_Interact.switchLogistics(\'' + f.id + '\',\'' + mode + '\')" style="padding:4px 12px;border:1px solid var(--border);border-radius:6px;background:' + (active ? 'var(--blue)' : 'var(--card)') + ';color:' + (active ? '#fff' : 'var(--text)') + ';cursor:pointer;font-size:12px">' + label + '</button>';
    });
    html += '</div>';

    // Timeline - enhanced
    var milestones = FP_Utils.getMilestoneDates(f);
    var doneCount = 0;
    milestones.forEach(function(ms) { if (festState.milestones[ms.id]) doneCount++; });
    var donePct = milestones.length > 1 ? (doneCount / (milestones.length - 1)) * 100 : 0;
    html += '<div class="fp-timeline">';
    html += '<div class="fp-timeline-line"><div class="fp-timeline-line-done" style="width:' + Math.min(donePct, 100) + '%"></div><div class="fp-timeline-line-todo" style="left:' + Math.min(donePct, 100) + '%;right:0"></div></div>';
    milestones.forEach(function(ms, idx) {
      var done = festState.milestones[ms.id];
      html += '<div class="fp-timeline-node">';
      html += '<div class="fp-timeline-dot' + (done ? ' done' : '') + '" onclick="FP_Interact.toggleMilestone(\'' + f.id + '\',\'' + ms.id + '\')" title="' + FP_Utils.escape(ms.actions) + '"></div>';
      html += '<span style="font-size:10px;color:var(--muted);text-align:center;white-space:nowrap">' + ms.name + '</span>';
      html += '<span style="font-size:11px;font-weight:600">' + ms.dateStr + '</span>';
      html += '<span style="font-size:9px;color:var(--blue);text-align:center;max-width:100px;line-height:1.2;margin-top:2px">' + ms.actions + '</span>';
      html += '</div>';
    });
    html += '</div>';

    // Status selector
    html += '<div style="display:flex;gap:4px;margin-bottom:10px;align-items:center;flex-wrap:wrap">';
    html += '<label style="font-size:12px;color:#6e6e73;margin-right:4px">状态：</label>';
    statusOptions.forEach(function(o) {
      var active = festState.status === o.v;
      html += '<button onclick="FP_Interact.setStatus(\'' + f.id + '\',\'' + o.v + '\')" style="padding:3px 10px;border:1px solid var(--border);border-radius:6px;background:' + (active ? o.c : 'var(--card)') + ';color:' + (active ? '#fff' : 'var(--text)') + ';cursor:pointer;font-size:11px">' + o.l + '</button>';
    });
    html += '</div>';

    // Products table with category filter
    html += '<div style="margin-bottom:12px">';
    // Category tabs
    var catCounts = {};
    f.products.forEach(function(p) { catCounts[p.category] = (catCounts[p.category] || 0) + 1; });
    var totalCats = Object.keys(catCounts).length;
    html += '<div style="display:flex;gap:4px;margin-bottom:8px;flex-wrap:wrap">';
    html += '<button onclick="FP_Interact.filterCat(\'' + f.id + '\',\'\',this)" class="cat-tab active" style="padding:3px 8px;border:1px solid #e5e5ea;border-radius:6px;background:var(--blue);color:#fff;cursor:pointer;font-size:11px">' + f.products.length + ' 全部</button>';
    Object.keys(catCounts).forEach(function(cat) {
      var catLabel = FP_CONFIG.categories[cat] ? FP_CONFIG.categories[cat].label : cat;
      html += '<button onclick="FP_Interact.filterCat(\'' + f.id + '\',\'' + cat + '\',this)" class="cat-tab" style="padding:3px 8px;border:1px solid #e5e5ea;border-radius:6px;background:var(--card);cursor:pointer;font-size:11px">' + catLabel + ' ' + catCounts[cat] + '</button>';
    });
    html += '</div>';
    // Table - enhanced
    html += '<div class="prod-list-' + f.id + '">';
    html += '<table class="fp-prod-table">';
    html += '<thead><tr><th>1688拿货</th><th>建议售价</th><th>毛利率</th><th>匹配度</th><th>风险</th><th>关键词（点击搜亚马逊）</th></tr></thead>';
    f.products.forEach(function(p) {
      var riskColor = p.riskLevel === "low" ? "var(--green)" : p.riskLevel === "medium" ? "var(--orange)" : "var(--red)";
      var riskBg = p.riskLevel === "low" ? "#f0fdf4" : p.riskLevel === "medium" ? "#fff7ed" : "#fef2f2";
      var kw = p.sourcing ? p.sourcing.replace("1688: ", "") : "";
      var amzKws = p.keywords && p.keywords.length > 0 ? p.keywords : [p.skuEn];
      // Extract margin number for color bar
      var marginNum = parseInt(p.margin) || 0;
      var barColor = marginNum >= 50 ? 'var(--green)' : marginNum >= 30 ? 'var(--orange)' : 'var(--red)';
      html += '<tr data-cat="' + p.category + '">';
      html += '<td><div style="font-weight:600">' + FP_Utils.escape(p.sku) + '</div><div style="color:var(--muted);font-size:11px">' + FP_Utils.escape(p.skuEn) + '</div></td>';
      html += '<td style="font-weight:600">' + p.priceRange + '</td>';
      html += '<td><div class="fp-profit-bar"><span style="font-weight:600;color:var(--green)">' + p.margin + '</span><div class="fp-profit-bar-bg"><div class="fp-profit-bar-fill" style="width:' + Math.min(marginNum, 100) + '%;background:' + barColor + '"></div></div></div></td>';
      html += '<td class="fp-stars">' + "★".repeat(p.matchScore) + '<span style="color:#d1d5db">' + "★".repeat(5 - p.matchScore) + '</span></td>';
      html += '<td><span style="padding:2px 8px;border-radius:8px;font-size:11px;font-weight:600;background:' + riskBg + ';color:' + riskColor + '">' + p.riskLevel + '</span></td>';
      html += '<td style="display:flex;gap:4px;flex-wrap:wrap">';
      amzKws.forEach(function(k) {
        html += '<a href="https://www.amazon.co.uk/s?k=' + encodeURIComponent(k) + '" target="_blank" style="display:inline-block;padding:2px 8px;border-radius:10px;font-size:10px;background:#FF950015;color:#FF9500;text-decoration:none;border:1px solid #FF950044;white-space:nowrap">' + FP_Utils.escape(k) + '</a>';
      });
      html += '<a href="https://s.1688.com/selloffer/offer_search.htm?keywords=' + encodeURIComponent(kw) + '&descSortType=5&sortType=booked" target="_blank" style="display:inline-block;padding:2px 8px;border-radius:10px;font-size:10px;background:#007AFF15;color:#007AFF;text-decoration:none;border:1px solid #007AFF44;white-space:nowrap">1688 ' + FP_Utils.escape(kw) + '</a>';
      html += '</td>';
      html += '</tr>';
    });
    html += '</table></div>';

    // Notes
    html += '<textarea style="width:100%;padding:8px;border:1px solid var(--border);border-radius:6px;font-size:12px;min-height:50px;resize:vertical;font-family:inherit;margin-bottom:10px" placeholder="备注..." oninput="FP_Interact.setNotes(\'' + f.id + '\',this.value)">' + FP_Utils.escape(festState.notes) + '</textarea>';

    // Validation
    if (f.validation) {
      html += '<div style="background:#eff6ff;border-radius:8px;padding:10px;margin-bottom:10px;font-size:12px">';
      html += '<div style="font-weight:600;color:var(--blue);margin-bottom:4px">验证指引</div>';
      if (f.validation.amazonCheck) html += '<div>亚马逊：' + FP_Utils.escape(f.validation.amazonCheck) + '</div>';
      if (f.validation.sourcing) html += '<div>1688：' + FP_Utils.escape(f.validation.sourcing) + '</div>';
      if (f.validation.riskFlags && f.validation.riskFlags.length) html += '<div>风险：' + f.validation.riskFlags.join("；") + '</div>';
      html += '</div>';
    }

    html += '</div></div>';
    return html;
  }
};

// Interact
var FP_Interact = {
  toggleCard: function(id) {
    FP_expandedCards[id] = !FP_expandedCards[id];
    var card = document.getElementById("card-" + id);
    if (card) {
      card.classList.toggle("expanded");
      var arrow = card.querySelector(".card-header span:last-child");
      if (arrow) arrow.innerHTML = FP_expandedCards[id] ? "&#9660;" : "&#9654;";
    }
  },
  switchLogistics: function(id, mode) {
    FP_State.updateFestival(id, { logistics: mode });
    FP_Render.dashboard();
    FP_Render.main();
  },
  toggleMilestone: function(id, mid) {
    FP_State.toggleMilestone(id, mid);
    FP_Render.dashboard();
    FP_Render.main();
  },
  setStatus: function(id, status) {
    FP_State.updateFestival(id, { status: status });
    FP_Render.dashboard();
    FP_Render.main();
  },
  setNotes: function(id, notes) {
    FP_State.updateFestival(id, { notes: notes });
  },
  filterCat: function(id, cat, el) {
    var card = document.getElementById("card-" + id);
    if (!card) return;
    card.querySelectorAll(".cat-tab").forEach(function(t) {
      t.style.background = "var(--card)";
      t.style.color = "var(--text)";
    });
    if (el) {
      el.style.background = cat ? "var(--card)" : "var(--blue)";
      el.style.color = cat ? "var(--text)" : "#fff";
    }
    card.querySelectorAll("tr[data-cat]").forEach(function(row) {
      row.style.display = cat && row.dataset.cat !== cat ? "none" : "";
    });
  },
  resetFilter: function() {
    FP_Filter.category = ""; FP_Filter.month = ""; FP_Filter.urgency = "";
    FP_Filter.status = ""; FP_Filter.search = ""; FP_Filter.statCardUrgency = "";
    document.getElementById("filterCategory").value = "";
    document.getElementById("filterMonth").value = "";
    document.getElementById("filterUrgency").value = "";
    document.getElementById("filterStatus").value = "";
    document.getElementById("filterSearch").value = "";
    FP_Render.main();
  }
};

// Init
function fpInit() {
  FP_State.load();
  FP_Render.monthNav();
  FP_Render.dashboard();
  FP_Render.main();
  ["filterCategory","filterMonth","filterUrgency","filterStatus"].forEach(function(id) {
    var el = document.getElementById(id);
    if (el) el.addEventListener("change", function() { FP_Render.main(); });
  });
  var s = document.getElementById("filterSearch");
  if (s) s.addEventListener("input", FP_Utils.debounce(function() { FP_Filter.search = s.value; FP_Render.main(); }, 180));
  var r = document.getElementById("resetFilter");
  if (r) r.addEventListener("click", function() { FP_Interact.resetFilter(); });
}

// Sync functions
var FP_SYNC_KEY = "uk_festival_sync_config";
function fpGetSync() { try { return JSON.parse(localStorage.getItem(FP_SYNC_KEY)) || {}; } catch(e) { return {}; } }
function fpSaveSync() {
  var t = document.getElementById("fpToken").value.trim();
  var g = document.getElementById("fpGistId").value.trim();
  localStorage.setItem(FP_SYNC_KEY, JSON.stringify({token:t,gistId:g}));
  document.getElementById("fpSyncStatus").textContent = "✅ 已保存！";
}
async function fpSyncCreate() {
  var t = document.getElementById("fpToken").value.trim();
  if (!t) { document.getElementById("fpSyncStatus").textContent = "❌ 请先填写Token"; return; }
  try {
    var r = await fetch("https://api.github.com/gists", {method:"POST",headers:{"Authorization":"Bearer "+t,"Content-Type":"application/json"},body:JSON.stringify({description:"Festival Planner Sync",public:false,files:{"data.json":{content:FP_State.export()}}})});
    var d = await r.json();
    document.getElementById("fpGistId").value = d.id;
    fpSaveSync();
    document.getElementById("fpSyncStatus").textContent = "✅ Gist创建成功！ID: "+d.id;
  } catch(e) { document.getElementById("fpSyncStatus").textContent = "❌ 错误: "+e.message; }
}
async function fpSyncPush() {
  var c = fpGetSync(); if (!c.token||!c.gistId) { document.getElementById("fpSyncStatus").textContent = "❌ 请先配置Token和Gist ID"; return; }
  try {
    await fetch("https://api.github.com/gists/"+c.gistId, {method:"PATCH",headers:{"Authorization":"Bearer "+c.token,"Content-Type":"application/json"},body:JSON.stringify({files:{"data.json":{content:FP_State.export()}}})});
    document.getElementById("fpSyncStatus").textContent = "✅ 推送成功！"+new Date().toLocaleString("zh-CN");
  } catch(e) { document.getElementById("fpSyncStatus").textContent = "❌ 错误: "+e.message; }
}
async function fpSyncPull() {
  var c = fpGetSync(); if (!c.token||!c.gistId) { document.getElementById("fpSyncStatus").textContent = "❌ 请先配置Token和Gist ID"; return; }
  try {
    var r = await fetch("https://api.github.com/gists/"+c.gistId, {headers:{"Authorization":"Bearer "+c.token}});
    var d = await r.json();
    FP_State.import(d.files["data.json"].content);
    FP_Render.dashboard(); FP_Render.main();
    document.getElementById("fpSyncStatus").textContent = "✅ 拉取成功！"+new Date().toLocaleString("zh-CN");
  } catch(e) { document.getElementById("fpSyncStatus").textContent = "❌ 错误: "+e.message; }
}
function fpExportJSON() {
  var b = new Blob([FP_State.export()], {type:"application/json"});
  var u = URL.createObjectURL(b);
  var a = document.createElement("a"); a.href = u; a.download = "festival-backup.json"; a.click();
}
function fpImportJSON(e) {
  var f = e.target.files[0]; if (!f) return;
  var r = new FileReader();
  r.onload = function(ev) { try { FP_State.import(ev.target.result); FP_Render.dashboard(); FP_Render.main(); alert("✅ 导入成功！"); } catch(err) { alert("❌ 导入失败: "+err.message); } };
  r.readAsText(f); e.target.value = "";
}
function fpExportCSV() {
  var rows = [["Month","Festival","Date","Importance","SKU","SKU EN","Category","Cost","Price","Margin","Match","Risk","Keywords"]];
  FESTIVALS.forEach(function(f) {
    f.products.forEach(function(p) {
      rows.push([f.month+"M",f.name,f.date,f.importance,p.sku,p.skuEn,p.category,p.costRange,p.priceRange,p.margin,p.matchScore+"/5",p.riskLevel,(p.keywords||[]).join("; ")]);
    });
  });
  var csv = "\uFEFF"+rows.map(function(r){return r.map(function(c){return "\""+String(c).replace(/"/g,"\"\"")+"\""}).join(",")}).join("\n");
  var b = new Blob([csv], {type:"text/csv;charset=utf-8"});
  var u = URL.createObjectURL(b);
  var a = document.createElement("a"); a.href = u; a.download = "festival-skus.csv"; a.click();
}
function fpResetAll() {
  if (!confirm("确定清除所有进度？此操作不可恢复！")) return;
  FP_State.reset(); FP_Render.dashboard(); FP_Render.main();
}
