const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => Array.from(el.querySelectorAll(s));
let CURRENT_RECO = { jobs: [], tours: [] }; // 엔진에서 받은 최신 카드 목록(농가/관광지)

// === 여기 추가 ===
function setupBadgeToggle(
  containerId,
  getInitial = () => [],
  onChange = () => {}
) {
  const box = document.getElementById(containerId);
  if (!box) return;

  // 초기 선택 복원
  const selected = new Set(getInitial());
  Array.from(box.querySelectorAll(".badge")).forEach((btn) => {
    if (selected.has(btn.textContent.trim())) btn.classList.add("active");
  });

  // 클릭 토글
  box.addEventListener("click", (e) => {
    const b = e.target.closest(".badge");
    if (!b) return;
    b.classList.toggle("active");
    const values = Array.from(box.querySelectorAll(".badge.active")).map((x) =>
      x.textContent.trim()
    );
    onChange(values);
  });
}

function hardReset() {
  try {
    localStorage.clear();
    caches?.keys?.().then((keys) => keys.forEach((k) => caches.delete(k)));
    navigator.serviceWorker
      ?.getRegistrations?.()
      .then((list) => list.forEach((r) => r.unregister()));
  } finally {
    location.reload();
  }
}

const STATE = {
  view: location.hash.replace("#", "") || "onboard",
  profile: JSON.parse(localStorage.getItem("ims_profile") || "{}"),
  prefs: JSON.parse(localStorage.getItem("ims_prefs") || "{}"),
  selections: JSON.parse(localStorage.getItem("ims_selections") || "{}"),
  history: JSON.parse(localStorage.getItem("ims_history") || "[]"),
  timeline: JSON.parse(localStorage.getItem("ims_timeline") || "[]"),
  calendar: JSON.parse(localStorage.getItem("ims_calendar") || "{}"),
  config: null,
  chatStage: "cards", // cards -> table
  chosenCards: [],
  user_id: localStorage.getItem("ims_user_id") || null,
  last_itinerary_id: localStorage.getItem("ims_itinerary_id") || null,
  last_schedule: JSON.parse(
    localStorage.getItem("ims_last_schedule") || "null"
  ),
};

async function loadConfig() {
  if (STATE.config) return STATE.config;
  // 현재 페이지 기준으로 config.json 절대경로 생성
  const base = location.origin + location.pathname.replace(/\/[^/]*$/, "/");
  const url = base + "config.json";
  console.log("[cfg] loading:", url);
  const res = await fetch(url, { cache: "no-cache" });
  if (!res.ok) throw new Error("config.json load failed: " + res.status);
  STATE.config = await res.json();
  return STATE.config;
}

function resolveEndpoint(pathOrKey, cfg) {
  if (!pathOrKey) return "";
  if (!String(pathOrKey).startsWith("/")) {
    return (cfg.endpoints && cfg.endpoints[pathOrKey]) || "";
  }
  return pathOrKey;
}
async function callEngine(pathOrKey, body) {
  const cfg = await loadConfig();
  const base = (cfg.baseURL || "").replace(/\/$/, "");
  const ep = resolveEndpoint(pathOrKey, cfg);
  if (!ep) throw new Error(`Unknown endpoint: ${pathOrKey}`);
  const url = `${base}${ep}`;

  const ac = new AbortController();
  const to = setTimeout(() => ac.abort(), Number(cfg.timeout_ms || 20000));

  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body || {}),
    signal: ac.signal,
  }).catch((e) => {
    clearTimeout(to);
    throw e;
  });
  clearTimeout(to);

  if (!res.ok) {
    const t = await res.text().catch(() => "");
    throw new Error(`HTTP ${res.status} ${url} :: ${t}`);
  }
  
  // 응답이 비어있거나 JSON이 아닐 경우 처리
  const responseText = await res.text();
  if (!responseText.trim()) {
    console.warn(`Empty response from ${url}`);
    return {};
  }
  
  try {
    return JSON.parse(responseText);
  } catch (e) {
    console.error(`JSON 파싱 실패 (${url}):`, responseText.substring(0, 100));
    throw new Error(`Invalid JSON response from ${url}: ${e.message}`);
  }
}

function buildOnboardingPayload() {
  const p = STATE.profile || {};
  const pf = STATE.prefs || {};
  return {
    real_name: p.real_name || p.nick || "",
    name: p.nick || "",
    age: p.age || "",
    gender: p.gender === "M" ? "남" : p.gender === "F" ? "여" : p.gender || "",
    sido: (p.region && p.region.sido) || p.sido || "",
    sigungu: (p.region && p.region.sigungu) || p.sigungu || "",
    with_whom: (p.with && p.with[0]) || p.with || "",
    selected_views: pf.scenery || [],
    selected_styles: pf.styles || [],
    selected_jobs: pf.jobs || [],
    additional_requests: pf.free || [],
  };
}
async function sendOnboardingAndGetUserId() {
  const cfg = await loadConfig();
  const hasOnboarding = cfg.endpoints && cfg.endpoints.onboarding;

  if (hasOnboarding) {
    const payload = buildOnboardingPayload();
    const data = await callEngine("onboarding", payload);
    if (data?.user_id) {
      STATE.user_id = data.user_id;
      saveState();
      return STATE.user_id;
    }
    throw new Error("onboarding API returned no user_id");
  } else {
    // 로컬 서버에 온보딩이 없을 때: 임시 user_id로 진행
    STATE.user_id = STATE.user_id || `local_${Date.now()}`;
    saveState();
    return STATE.user_id;
  }
}

// 엔진 추천만 호출(폴백 없음) + 에러 표면화
async function engineRecommend(natural_request) {
  const cfg = await loadConfig();
  const endpoints = cfg.endpoints || {};
  const path =
    endpoints.recommendations || endpoints["recommendations/with-user"];
  if (!path)
    throw new Error(
      "config.json: endpoints.recommendations(또는 recommendations/with-user) 누락"
    );

  if (!STATE.user_id && typeof sendOnboardingAndGetUserId === "function") {
    await sendOnboardingAndGetUserId();
  }

  const url = cfg.baseURL + path;
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      user_id: STATE.user_id || "local_user",
      natural_request,
    }),
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return await res.json(); // { status, data: { farms, tour_spots, ... } }
}

function saveState() {
  localStorage.setItem("ims_profile", JSON.stringify(STATE.profile));
  localStorage.setItem("ims_prefs", JSON.stringify(STATE.prefs));
  localStorage.setItem("ims_selections", JSON.stringify(STATE.selections));
  localStorage.setItem("ims_history", JSON.stringify(STATE.history));
  localStorage.setItem("ims_timeline", JSON.stringify(STATE.timeline));
  localStorage.setItem("ims_calendar", JSON.stringify(STATE.calendar));
  localStorage.setItem("ims_user_id", STATE.user_id || "");
  localStorage.setItem("ims_itinerary_id", STATE.last_itinerary_id || "");
  localStorage.setItem(
    "ims_last_schedule",
    JSON.stringify(STATE.last_schedule || null)
  );
}

function navigate(v) {
  STATE.view = v;
  location.hash = v;
  render();
}
window.addEventListener("hashchange", () => {
  STATE.view = location.hash.replace("#", "") || "onboard";
  render();
});

/* --------- Drawer --------- */
function renderDrawer() {
  const el = $(".drawer");
  el.innerHTML = `
    <div class="backdrop" id="closeDrawer"></div>
    <div class="panel">
      <div class="brand"><span class="pill">🌱</span> 기록</div>
      <div class="muted" style="margin:6px 0 12px 0">대화/일정 기록</div>
      <div id="historyList"></div>
      <div style="height:14px"></div>
      <button class="btn ghost" id="closeBtn">닫기</button>
    </div>`;
  $("#closeDrawer").onclick = () => el.classList.remove("open");
  $("#closeBtn").onclick = () => el.classList.remove("open");
  renderHistoryList();
}
function renderHistoryList() {
  const list = $("#historyList");
  const items = STATE.history;
  if (items.length === 0) {
    list.innerHTML = `<div class="notice">아직 기록이 없습니다.</div>`;
    return;
  }
  list.innerHTML = items
    .map(
      (h, i) => `
    <div class="history-item" data-idx="${i}">
      <div style="font-weight:800">${h.title || "기록 " + (i + 1)}</div>
      <div class="muted" style="white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${(
        h.preview || ""
      ).slice(0, 100)}</div>
      <small class="key">${h.date || ""}</small>
    </div>`
    )
    .join("");
  $$("#historyList .history-item").forEach((el) => {
    el.onclick = () => {
      const idx = +el.dataset.idx;
      const rec = STATE.history[idx];
      if (rec && rec.timeline) {
        STATE.timeline = rec.timeline;
        upsertCalendarEvents(rec.timeline);
        saveState();
        $(".drawer").classList.remove("open");
        navigate("chat");
      }
    };
  });
}

/* --------- Header --------- */
function renderHeader() {
  const el = $(".header");
  el.innerHTML = `
    <div class="logo" style="display:flex;align-items:center;gap:8px">
      <img src="./assets/icons/imsm_logo_w.png"
           style="height:28px;object-fit:contain;display:block" />
    </div>
    <button class="hamburger" id="openDrawer">☰</button>
  `;
  $("#openDrawer").onclick = () => {
    $(".drawer").classList.add("open");
    renderDrawer();
  };
}

/* --------- Calendar Tools --------- */
function monthMatrix(year, month) {
  const first = new Date(year, month, 1);
  const start = new Date(first);
  start.setDate(first.getDate() - ((first.getDay() + 6) % 7));
  let days = [];
  for (let i = 0; i < 42; i++) {
    const dt = new Date(start);
    dt.setDate(start.getDate() + i);
    days.push({
      d: dt.getDate(),
      inMonth: dt.getMonth() === month,
      key: dt.toISOString().slice(0, 10),
    });
  }
  return days;
}
function calendarBlocksHTML(year, month) {
  const days = monthMatrix(year, month);
  const mm = (month + 1).toString().padStart(2, "0");
  const yymm = year + "-" + mm;
  const cal = STATE.calendar[yymm] || {};
  return `
    <div class="cal-head">
      <button class="btn ghost" id="prevMonth">◀</button>
      <div style="font-weight:900;font-size:20px">${year}년 ${month + 1}월</div>
      <button class="btn ghost" id="nextMonth">▶</button>
    </div>
    <div class="cal-grid">
      ${["월", "화", "수", "목", "금", "토", "일"]
        .map(
          (w) =>
            `<div style="text-align:center;font-weight:800;color:#9aa0a6">${w}</div>`
        )
        .join("")}
      ${days
        .map((d) => {
          const has = !!cal[d.key];
          return `<div class="cal-cell ${d.inMonth ? "" : "muted"} ${
            has ? "has" : ""
          }" data-date="${d.key}">
          <div>${d.d}</div>${has ? '<div class="dot"></div>' : ""}</div>`;
        })
        .join("")}
    </div>`;
}
function upsertCalendarEvents(timeline) {
  (timeline || []).forEach((item) => {
    const key = (item.datetime || "").slice(0, 10);
    if (!key) return;
    const yymm = key.slice(0, 7);
    STATE.calendar[yymm] = STATE.calendar[yymm] || {};
    STATE.calendar[yymm][key] = STATE.calendar[yymm][key] || [];
    STATE.calendar[yymm][key].push(item);
  });
  saveState();
}

/* --------- Engine --------- */
async function callEngine(kind, payload) {
  const cfg = await loadConfig();
  const url = cfg.baseURL + (cfg.endpoints[kind] || "/" + kind);
  try {
    const res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) throw new Error("HTTP " + res.status);
    return await res.json();
  } catch (e) {
    console.warn("Engine fallback:", e.message);
    return mockPlan(payload);
  }
}
function mockPlan(payload) {
  const now = new Date();
  const day = new Date(now.getFullYear(), now.getMonth(), now.getDate() + 2);
  const d = (yy) => {
    const y = yy.getFullYear(),
      m = String(yy.getMonth() + 1).padStart(2, "0"),
      d = String(yy.getDate()).padStart(2, "0"),
      hh = String(yy.getHours()).padStart(2, "0"),
      mm = String(yy.getMinutes()).padStart(2, "0");
    return `${y}-${m}-${d}T${hh}:${mm}:00`;
  };
  const a = new Date(day);
  a.setHours(8, 0);
  const b = new Date(day);
  b.setHours(12, 0);
  const c = new Date(day);
  c.setHours(15, 0);
  return {
    timeline: [
      {
        datetime: d(a),
        title: "사과 수확 돕기",
        location: "전북 김제시 봉남면",
        desc: "농장 도우미",
        icon: "🍎",
      },
      {
        datetime: d(b),
        title: "시장 투어 & 점심",
        location: "전주 남부시장",
        desc: "칼국수 추천",
        icon: "🍜",
      },
      {
        datetime: d(c),
        title: "내장산 산책",
        location: "정읍시",
        desc: "힐링 트레일",
        icon: "⛰️",
      },
    ],
    suggestions: ["힐링 테마 여행", "농촌 체험", "사진 스팟"],
  };
}

async function createScheduleWithUser({
  natural_request,
  selected_farm,
  selected_tours,
}) {
  if (!STATE.user_id) await sendOnboardingAndGetUserId();
  const body = {
    user_id: STATE.user_id,
    natural_request,
    selected_farm,
    selected_tours,
  };
  const data = await callEngine("plan", body); // POST /api/schedule/with-user
  const sched = data?.data || data || {};

  if (sched?.itinerary_id) {
    STATE.last_itinerary_id = sched.itinerary_id;
    STATE.last_schedule = sched;
    STATE.timeline =
      sched.bubble_schedule?.grouped_schedule || sched.itinerary || [];
    STATE.calendar = sched.bubble_schedule?.calendar_events || {};
  } else {
    STATE.last_schedule = sched;
    STATE.timeline = sched?.timeline || [];
    STATE.calendar = sched?.calendar || {};
  }
  saveState();
  return sched;
}
async function sendScheduleFeedback(feedback) {
  if (!STATE.user_id) await sendOnboardingAndGetUserId();
  const body = { user_id: STATE.user_id, feedback };
  const data = await callEngine("revise", body); // POST /api/schedule/feedback
  const sched = data?.data || data || {};

  if (sched?.itinerary_id) {
    STATE.last_itinerary_id = sched.itinerary_id;
    STATE.last_schedule = sched;
    STATE.timeline =
      sched.bubble_schedule?.grouped_schedule || sched.itinerary || [];
    STATE.calendar = sched.bubble_schedule?.calendar_events || {};
  } else {
    STATE.last_schedule = sched;
    STATE.timeline = sched?.timeline || [];
    STATE.calendar = sched?.calendar || {};
  }
  saveState();
  return sched;
}
async function confirmSchedule() {
  if (!STATE.user_id) await sendOnboardingAndGetUserId();
  const body = {
    user_id: STATE.user_id,
    itinerary_id: STATE.last_itinerary_id,
    calendar_events: STATE.calendar,
  };
  return callEngine("confirm", body); // POST /confirm
}

/* --------- Home --------- */
function renderMiniTime() {
  if (!STATE.last_schedule?.itinerary || STATE.last_schedule.itinerary.length === 0)
    return `<div class="muted">아직 생성된 여행 일정이 없습니다.</div>`;
  
  // chat 화면의 '생성된 여행 일정'과 동일한 형태로 표시
  const itinerary = STATE.last_schedule.itinerary;
  
  // 일정 그룹화 (농가는 연속으로, 관광지는 같은 날짜끼리)
  const groupedSchedule = [];
  let currentGroup = null;

  itinerary.forEach(item => {
    if (item.schedule_type === "농가") {
      if (currentGroup && currentGroup.type === "농가") {
        // 기존 농가 그룹에 추가
        currentGroup.endDay = item.day;
        currentGroup.items.push(item);
      } else {
        // 새로운 농가 그룹 시작
        if (currentGroup) groupedSchedule.push(currentGroup);
        currentGroup = {
          type: "농가",
          startDay: item.day,
          endDay: item.day,
          items: [item]
        };
      }
    } else {
      // 관광지는 같은 날짜끼리 그룹화
      if (currentGroup && currentGroup.type === "관광지" && currentGroup.startDay === item.day) {
        // 같은 날짜의 관광지 그룹에 추가
        currentGroup.items.push(item);
      } else {
        // 새로운 관광지 그룹 시작
        if (currentGroup) groupedSchedule.push(currentGroup);
        currentGroup = {
          type: "관광지",
          startDay: item.day,
          endDay: item.day,
          items: [item]
        };
      }
    }
  });

  // 마지막 그룹 추가
  if (currentGroup) groupedSchedule.push(currentGroup);

  return `
    <div class="schedule-table">
      ${groupedSchedule.map(group => {
        const dayRange = group.startDay === group.endDay 
          ? `Day ${group.startDay}` 
          : `Day ${group.startDay} ~ ${group.endDay}`;
        
        const firstItem = group.items[0];
        
        return `
          <div class="schedule-item">
            <div class="schedule-day">${dayRange}</div>
            <div class="schedule-content">
              <div class="schedule-date-with-type">
                <span class="schedule-date">${firstItem.date}</span>
                <span class="schedule-type${firstItem.schedule_type === '관광지' ? ' tour' : ''}">${firstItem.schedule_type}</span>
              </div>
              
              ${group.type === "농가" ? 
                // 농가는 중복 제거하여 한 번만 표시
                (() => {
                  const uniqueItems = [];
                  const seen = new Set();
                  group.items.forEach(item => {
                    const key = `${item.name}-${item.address}`;
                    if (!seen.has(key)) {
                      seen.add(key);
                      uniqueItems.push(item);
                    }
                  });
                  return uniqueItems.map(item => `
                    <div class="schedule-place">
                      <div class="schedule-name">${item.name}</div>
                      <div class="schedule-details">
                        <span class="schedule-time">${item.start_time || ''}</span>
                        <span class="schedule-address">${item.address || ''}</span>
                      </div>
                    </div>
                  `).join('');
                })()
                :
                // 관광지는 모든 항목 표시
                group.items.map(item => `
                  <div class="schedule-place">
                    <div class="schedule-name">${item.name}</div>
                    <div class="schedule-details">
                      <span class="schedule-time">${item.start_time || ''}</span>
                      <span class="schedule-address">${item.address || ''}</span>
                    </div>
                  </div>
                `).join('')
              }
            </div>
          </div>
        `;
      }).join('')}
    </div>
  `;
}
function renderHome() {
  const now = new Date();
  const y = Number(localStorage.getItem("ims_year")) || now.getFullYear();
  const m = Number(localStorage.getItem("ims_month")) || now.getMonth();
  const c = $(".container");
  c.innerHTML = `
    <div class="card">
      </div>
      <div class="calendar" id="calendar">${calendarBlocksHTML(y, m)}</div>
      <div style="height:8px"></div>
      <div class="section-title" style="text-align:center">나만의 맞춤형 AI 여행 플래너</div>
      <div class="inputbar" style="position:static;border:none;padding:0;margin-top:8px">
        <input class="input" id="homeQuery" placeholder="어떤 곳으로 떠나고 싶으신가요?">
        <button class="btn" id="goChat">▶</button>
      </div>
    </div>
    <div style="height:12px"></div>
    <div class="card">
      <div class="tabs"><div class="tab active">여행요약</div><div class="tab">상세일정</div><div class="tab">일손매칭내역</div></div>
      <div id="miniTime">${renderMiniTime()}</div>
    </div>`;
  $("#goChat").onclick = async () => {
    const q = $("#homeQuery").value.trim();
    if (q) {
      localStorage.setItem("ims_home_query", q);
      $("#homeQuery").value = ""; // 홈 입력창 초기화
      navigate("chat");
    } else {
      navigate("chat");
    }
  };
  $("#prevMonth").onclick = () => {
    let yy = y,
      mm = m - 1;
    if (mm < 0) {
      mm = 11;
      yy--;
    }
    localStorage.setItem("ims_year", yy);
    localStorage.setItem("ims_month", mm);
    renderHome();
  };
  $("#nextMonth").onclick = () => {
    let yy = y,
      mm = m + 1;
    if (mm > 11) {
      mm = 0;
      yy++;
    }
    localStorage.setItem("ims_year", yy);
    localStorage.setItem("ims_month", mm);
    renderHome();
  };
  $$(".cal-cell.inMonth").forEach((cell) => {
    cell.onclick = () => {
      const date = cell.dataset.date;
      const yymm = date.slice(0, 7);
      const items = (STATE.calendar[yymm] || {})[date] || [];
      alert(
        items.length
          ? items
              .map((i) => `${i.datetime.slice(11, 16)} ${i.title}`)
              .join("\\n")
          : "이 날짜에는 일정이 없습니다."
      );
    };
  });
}

// 로딩 표시 함수
function showLoading(message = "분석 중...") {
  const loading = document.createElement("div");
  loading.className = "msg bot loading";
  loading.id = "loadingMsg";
  loading.innerHTML = `
    <div style="display: flex; align-items: center; gap: 8px;">
      <div class="spinner"></div>
      <span>${message}</span>
    </div>
  `;
  $("#chat").appendChild(loading);
  $("#chat").scrollTop = $("#chat").scrollHeight;
}

function hideLoading() {
  const loading = $("#loadingMsg");
  if (loading) loading.remove();
}

// 추천 API 호출 함수 (재사용)
async function triggerRecommendation(natural_request, skipUserMessage = false) {
  try {
    if (!skipUserMessage) {
      addMsg(natural_request, true);
    }
    showLoading("조건을 분석 중입니다...");

    const reco = await engineRecommend(natural_request);
    console.log("[recommendations] raw:", reco);

    const farms = reco?.data?.farms || [];
    const tours = reco?.data?.tour_spots || [];

    hideLoading();
    
    if (!farms.length && !tours.length) {
      addMsg("조건에 맞는 추천이 없어요. 기간/지역을 조금 넓혀볼까요?");
      return;
    }

    const farmCards = farms.map((f) => ({
      id: f.farm_id || f.id || crypto.randomUUID(),
      title: f.title || f.farm || "농가 체험",
      location: f.address || "",
      img: f.photo || "",
      time: `${f.start_time || "08:00"} - ${f.end_time || "17:00"}`,
      people: f.required_people || "",
      kind: "jobs",
      raw: f,
    }));

    const tourCards = tours.map((t) => ({
      id: t.tour_id || t.contentid || t.id || crypto.randomUUID(),
      title: t.name || "관광지",
      location: t.address || "",
      img: t.photo || "",
      kind: "tours",
      raw: t,
    }));

    CURRENT_RECO = { jobs: farmCards, tours: tourCards };

    $("#cardsWrap").innerHTML = `
      ${renderCardsSection(
        "추천! 농촌 체험 및 소일거리",
        CURRENT_RECO.jobs,
        "jobs"
      )}
      ${renderCardsSection("추천! 힐링 테마 여행", CURRENT_RECO.tours, "tours")}
      <div style="height:8px"></div>
      <button class="btn" id="makePlan">선택한 카드로 일정 생성하기</button>
    `;

    bindCardActions();
    $("#pickedWrap").innerHTML = renderPicked();

    $("#makePlan").onclick = async () => {
      const btn = $("#makePlan");
      btn.disabled = true;
      showLoading("일정을 생성하고 있습니다...");
      
      const payload = {
        user_id: STATE.user_id || "local_user",
        natural_request: natural_request,
        selected_farm: (STATE.chosenCards.find((c) => c.kind === "jobs") || {})
          .raw,
        selected_tours: STATE.chosenCards
          .filter((c) => c.kind === "tours")
          .map((c) => c.raw),
      };
      try {
        const sched = await createScheduleWithUser(payload);
        hideLoading();
        btn.remove(); // 버튼 삭제
        
        STATE.chatStage = "table";
        saveState();
        renderScheduleTable(sched);
      } catch (e) {
        console.error("일정 생성 에러:", e);
        hideLoading();
        
        if (e.message.includes("Invalid JSON")) {
          addMsg("서버 응답 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.");
        } else if (e.message.includes("HTTP")) {
          addMsg("서버 연결에 문제가 있습니다. 네트워크 상태를 확인해 주세요.");
        } else {
          addMsg("일정 생성에 실패했어요. 다시 시도해 주세요.");
        }
        
        btn.disabled = false;
      }
    };
  } catch (e) {
    console.warn("recommendations error:", e);
    hideLoading();
    addMsg(
      `추천을 불러오지 못했어요. 서버 연결을 확인해 주세요. (${e.message})`
    );
  }
}

// 엔진에만 붙는 추천 API (폴백 없음)
async function engineRecommend(natural_request) {
  const cfg = await loadConfig();
  const path =
    cfg.endpoints &&
    (cfg.endpoints.recommendations ||
      cfg.endpoints["recommendations/with-user"]);
  if (!path)
    throw new Error("config.json에 recommendations 엔드포인트가 없습니다.");

  if (!STATE.user_id && typeof sendOnboardingAndGetUserId === "function") {
    await sendOnboardingAndGetUserId();
  }
  const url = cfg.baseURL + path;
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      user_id: STATE.user_id || "local_user",
      natural_request,
    }),
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return await res.json(); // { status, data: { farms, tour_spots, ... } }
}

/* --------- Chat (Cards -> Table) --------- */
/** 선택 상태 (농가 1개 + 관광 N개 유지) */
STATE.selections = STATE.selections || { farm: null, tours: [] };
STATE.chosenCards = STATE.chosenCards || []; // 화면 상단 ‘선택한 카드’ 표시용(옵션)

/** 추천 결과를 카드 도메인 모델로 통일 */
function normalizeCards(reco) {
  const farms = (reco?.data?.farms || []).map((f) => ({
    kind: "jobs",
    id: f.farm_id,
    title: f.title || f.farm,
    location: f.address || "",
    img: f.photo || "",
    raw: f,
  }));
  const tours = (reco?.data?.tour_spots || []).map((t) => ({
    kind: "tours",
    id: t.tour_id,
    title: t.name,
    location: t.address || "",
    img: t.photo || "",
    raw: t,
  }));
  return { farms, tours, target_region: reco?.data?.target_region || "" };
}

/** 카드 UI 템플릿 */
function renderCardsSection(title, list, key) {
  return `<div class="section-title">${title}</div>
  <div class="carousel">${list
    .map(
      (x) => `
    <div class="cardItem ${x.kind}" data-id="${x.id}" data-kind="${x.kind}">
      <div class="cardImg" style="background-image:url('${x.img || ""}')"></div>
      <div class="cardBody">
        <div class="cardTitle">${x.title}</div>
        <div class="cardLoc">${x.location || ""}</div>
        <div class="cardFoot">
          <span class="kit">${
            x.kind === "jobs" || x.kind === "farm" ? "농가" : "관광지"
          }</span>
          <label class="checkbox-container">
            <input type="checkbox" class="card-checkbox" data-id="${
              x.id
            }" data-kind="${x.kind}">
            <span class="checkmark"></span>
          </label>
        </div>
      </div>
    </div>`
    )
    .join("")}</div>`;
}

/** 상단 '선택한 카드' 간단 표시 */
function renderPicked() {
  const f = STATE.selections.farm ? [STATE.selections.farm.title] : [];
  const t = (STATE.selections.tours || []).map((x) => x.title);
  const all = f.concat(t);
  if (!all.length) return "";
  return `<div class="muted">선택한 카드: ${all.join(", ")}</div>`;
}

/** 카드 DOM에 선택상태 반영 */
function syncCardActiveState() {
  // 농가: 단일 선택
  $$(".cardItem.farm").forEach((el) => {
    const id = el.dataset.id;
    el.classList.toggle(
      "active",
      STATE.selections.farm && STATE.selections.farm.id === id
    );
  });
  // 관광지: 다중 선택
  $$(".cardItem.tour").forEach((el) => {
    const id = el.dataset.id;
    el.classList.toggle(
      "active",
      (STATE.selections.tours || []).some((t) => t.id === id)
    );
  });
  const btn = $("#btnMakeSchedule");
  if (btn) btn.disabled = !STATE.selections.farm; // 농가 필수
  const picked = $("#pickedWrap");
  if (picked) picked.innerHTML = renderPicked();
}

/** 카드 체크박스 바인딩 */
function bindCardActions() {
  $$(".card-checkbox").forEach((checkbox) => {
    checkbox.onchange = (e) => {
      const checkbox = e.target;
      const id = checkbox.dataset.id;
      const kind = checkbox.dataset.kind;

      if (checkbox.checked) {
        // 농가 카드는 단일 선택만 허용
        if (kind === "jobs") {
          // 기존 농가 선택 해제
          $$(".card-checkbox[data-kind='jobs']").forEach((cb) => {
            if (cb !== checkbox) {
              cb.checked = false;
            }
          });
          // STATE에서 기존 농가 카드 제거
          STATE.chosenCards = STATE.chosenCards.filter(
            (c) => c.kind !== "jobs"
          );
        }

        // 새 카드 추가
        const pool = kind === "jobs" ? CURRENT_RECO.jobs : CURRENT_RECO.tours;
        const item = pool.find((x) => x.id === id);
        if (item && !STATE.chosenCards.some((c) => c.id === id)) {
          STATE.chosenCards.push({ 
            ...item, 
            kind: kind,
            raw: item  // 원본 데이터 저장
          });
        }
      } else {
        // 카드 선택 해제
        STATE.chosenCards = STATE.chosenCards.filter((c) => c.id !== id);
      }

      $("#pickedWrap").innerHTML = renderPicked();
      saveState();
    };
  });
}

/** 채팅 메시지 유틸 */
function addMsg(text, me = false) {
  const div = document.createElement("div");
  div.className = "msg " + (me ? "me" : "bot");
  div.textContent = text;
  $("#chat").appendChild(div);
  $("#chat").scrollTop = $("#chat").scrollHeight;
}

/** 개선된 스케줄 테이블 렌더링 */
function renderScheduleTable(sched) {
  const container = $("#tableWrap");
  const itinerary = sched?.itinerary || [];
  
  if (!itinerary.length) {
    container.innerHTML = '<div class="muted">일정이 생성되지 않았습니다.</div>';
    return;
  }

  // 일정 그룹화 (농가는 연속으로, 관광지는 같은 날짜끼리)
  const groupedSchedule = [];
  let currentGroup = null;

  itinerary.forEach(item => {
    if (item.schedule_type === "농가") {
      if (currentGroup && currentGroup.type === "농가") {
        // 기존 농가 그룹에 추가
        currentGroup.endDay = item.day;
        currentGroup.items.push(item);
      } else {
        // 새로운 농가 그룹 시작
        if (currentGroup) groupedSchedule.push(currentGroup);
        currentGroup = {
          type: "농가",
          startDay: item.day,
          endDay: item.day,
          items: [item]
        };
      }
    } else {
      // 관광지는 같은 날짜끼리 그룹화
      if (currentGroup && currentGroup.type === "관광지" && currentGroup.startDay === item.day) {
        // 같은 날짜의 관광지 그룹에 추가
        currentGroup.items.push(item);
      } else {
        // 새로운 관광지 그룹 시작
        if (currentGroup) groupedSchedule.push(currentGroup);
        currentGroup = {
          type: "관광지",
          startDay: item.day,
          endDay: item.day,
          items: [item]
        };
      }
    }
  });

  // 마지막 그룹 추가
  if (currentGroup) groupedSchedule.push(currentGroup);

  container.innerHTML = `
    <div class="section-title">생성된 여행 일정</div>
    <div class="schedule-table">
      ${groupedSchedule.map(group => {
        const dayRange = group.startDay === group.endDay 
          ? `Day ${group.startDay}` 
          : `Day ${group.startDay} ~ ${group.endDay}`;
        
        const firstItem = group.items[0];
        
        return `
          <div class="schedule-item">
            <div class="schedule-day">${dayRange}</div>
            <div class="schedule-content">
              <div class="schedule-date-with-type">
                <span class="schedule-date">${firstItem.date}</span>
                <span class="schedule-type${firstItem.schedule_type === '관광지' ? ' tour' : ''}">${firstItem.schedule_type}</span>
              </div>
              
              ${group.type === "농가" ? 
                // 농가는 중복 제거하여 한 번만 표시
                (() => {
                  const uniqueItems = [];
                  const seen = new Set();
                  group.items.forEach(item => {
                    const key = `${item.name}-${item.address}`;
                    if (!seen.has(key)) {
                      seen.add(key);
                      uniqueItems.push(item);
                    }
                  });
                  return uniqueItems.map(item => `
                    <div class="schedule-place">
                      <div class="schedule-name">${item.name}</div>
                      <div class="schedule-details">
                        <span class="schedule-time-tag">${item.start_time || ''}</span>
                        <span class="schedule-address">${item.address || ''}</span>
                      </div>
                    </div>
                  `).join('');
                })()
                :
                // 관광지는 모든 항목 표시
                group.items.map(item => `
                  <div class="schedule-place">
                    <div class="schedule-name">${item.name}</div>
                    <div class="schedule-details">
                      <span class="schedule-time-tag">${item.start_time || ''}</span>
                      <span class="schedule-address">${item.address || ''}</span>
                    </div>
                  </div>
                `).join('')
              }
            </div>
          </div>
        `;
      }).join('')}
    </div>
  `;
}

/** 타임테이블 렌더(그룹드 우선) - 기존 함수 유지 */
function renderTableFromSchedule(sched) {
  const container = $("#tableWrap");
  const groups = sched?.bubble_schedule?.grouped_schedule || [];
  const tl = sched?.timeline || [];
  if (groups.length) {
    container.innerHTML = groups
      .map(
        (g) => `
      <div class="card timetable">
        <div class="item">
          <div class="bullet"></div>
          <div>
            <div class="cardTitle">${g.title}</div>
            <div class="muted">${g.subtitle || ""}</div>
            <div class="muted">${g.date || ""} ${g.start_time || ""}</div>
          </div>
        </div>
      </div>
    `
      )
      .join("");
  } else if (tl.length) {
    container.innerHTML = tl
      .map(
        (it) => `
      <div class="card timetable">
        <div class="item">
          <div class="bullet"></div>
          <div>
            <div class="cardTitle">${it.title}</div>
            <div class="muted">${it.location || ""}</div>
            <div class="muted">${it.datetime || ""}</div>
          </div>
        </div>
      </div>
    `
      )
      .join("");
  } else {
    container.innerHTML = "";
  }
}

/** 미니 캘린더 렌더링 (홈 화면, 여행 요약에서 사용) */
function renderMiniCalendar(events, container, title = "캘린더") {
  // events: [{ date:"10/01/2025 9:00 am", activity:"...", day:1, type:"관광지" }, ...]
  const cal = document.createElement("div");
  cal.className = "card";
  const list = (events || [])
    .slice(0, 20)
    .map(
      (ev) => `
    <div class="item" style="display:grid;grid-template-columns:20px 1fr;gap:8px;padding:6px 0;border-bottom:1px dashed #e5e7eb">
      <div class="bullet"></div>
      <div>
        <div class="cardTitle">${ev.activity}</div>
        <div class="muted">${ev.date} • ${ev.type || ""}</div>
      </div>
    </div>
  `
    )
    .join("");
  cal.innerHTML = `
    <div class="section-title">${title}</div>
    <div class="timetable">${list}</div>
  `;
  
  if (container) {
    container.appendChild(cal);
  }
  
  return cal;
}

/** 홈 캘린더 업데이트 (일정 확정 시 호출) */
function updateHomeCalendar() {
  if (!STATE.last_schedule?.itinerary) return;
  
  // 일정을 캘린더 이벤트로 변환
  STATE.last_schedule.itinerary.forEach(item => {
    if (item.date && item.name) {
      // 날짜를 YYYY-MM-DD 형태로 변환
      const dateStr = item.date;
      const yearMonth = dateStr.slice(0, 7); // YYYY-MM
      const day = dateStr.slice(8, 10); // DD
      
      // 캘린더 데이터 구조에 맞게 저장
      STATE.calendar[yearMonth] = STATE.calendar[yearMonth] || {};
      STATE.calendar[yearMonth][day] = STATE.calendar[yearMonth][day] || [];
      
      // 중복 방지
      const exists = STATE.calendar[yearMonth][day].some(event => 
        event.activity === item.name && event.type === item.schedule_type
      );
      
      if (!exists) {
        STATE.calendar[yearMonth][day].push({
          activity: item.name,
          date: item.date + (item.start_time ? ` ${item.start_time}` : ''),
          type: item.schedule_type,
          day: item.day
        });
      }
    }
  });
  
  // 로컬스토리지에 저장
  localStorage.setItem("ims_calendar", JSON.stringify(STATE.calendar));
}

/** 전역 카드 풀: 현재 추천 결과를 담아 클릭 시 원본 참조 */
let CURRENT_CARD_POOL = [];

/** 추천 → 카드 그리기 */
async function fetchAndRenderRecommendations(natural) {
  // 1) 사용자 발화 표시
  if (natural) addMsg(natural, true);

  // 2) 추천 호출
  let reco;
  try {
    // user_id 자동 확보(온보딩 API 없으면 local_로 폴백)
    if (!STATE.user_id) await sendOnboardingAndGetUserId();
    reco = (await getRecommendations)
      ? await getRecommendations(natural)
      : null;
  } catch (e) {
    console.warn("recommendations error:", e);
  }

  // 3) 추천 없으면 안내
  if (!reco || reco?.status === "error") {
    addMsg("추천을 불러오지 못했어요. 조건을 바꿔 다시 시도해볼까요?");
    return;
  }

  // 4) 카드로 변환 + 렌더
  const { farms, tours, target_region } = normalizeCards(reco);
  CURRENT_CARD_POOL = farms.concat(tours);

  $("#cardsWrap").innerHTML = `
    ${
      farms.length
        ? renderCardsSection("추천! 농촌 체험 및 소일거리", farms, "farms")
        : ""
    }
    ${
      tours.length
        ? renderCardsSection("추천! 힐링 테마 여행", tours, "tours")
        : ""
    }
    <div style="height:8px"></div>
    <button class="btn btn-lg" id="btnMakeSchedule" ${
      STATE.selections.farm ? "" : "disabled"
    }>선택한 카드로 일정 생성</button>
  `;
  $("#pickedWrap").innerHTML = renderPicked();

  bindCardActions();
  syncCardActiveState();

  // 5) 지역 안내 메시지
  if (target_region) addMsg(`추천 지역: ${target_region} 일대로 구성해볼게요.`);
}

/** 선택 카드 기반 일정 생성 */
async function generateFromSelections() {
  const btn = $("#btnMakeSchedule");
  if (!STATE.selections.farm) {
    alert("먼저 농가 카드를 선택해주세요.");
    return;
  }
  const natural_request = ($("#chatInput")?.value || "").trim();
  btn.disabled = true;
  const old = btn.textContent;
  btn.textContent = "일정 생성 중…";
  try {
    const sched = await createScheduleWithUser({
      natural_request,
      selected_farm: STATE.selections.farm?.raw || STATE.selections.farm, // 엔진에 원본 구조 전달
      selected_tours: (STATE.selections.tours || []).map((t) => t.raw || t),
    });
    addMsg(
      "타임테이블을 생성했어요. 수정이 필요하면 아래에 자연어로 말씀해 주세요!"
    );
    renderTableFromSchedule(sched);
    updateHomeCalendar();
    renderHomeTimeline();
  } catch (e) {
    console.error("일정 생성 에러:", e);
    
    if (e.message.includes("Invalid JSON")) {
      alert("서버 응답 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.");
    } else if (e.message.includes("HTTP")) {
      alert("서버 연결에 문제가 있습니다. 네트워크 상태를 확인해 주세요.");
    } else {
      alert("일정 생성에 실패했습니다. 다시 시도해 주세요.");
    }
  } finally {
    btn.disabled = false;
    btn.textContent = old;
  }
}

/** 피드백 처리 함수 */
async function handleScheduleFeedback(feedback) {
  addMsg(feedback, true);
  showLoading("일정을 수정하고 있습니다...");
  
  try {
    const sched = await sendScheduleFeedback(feedback);
    hideLoading();
    addMsg("요청하신 내용으로 일정을 수정했어요.");
    renderScheduleTable(sched);
  } catch (e) {
    console.error("일정 수정 에러:", e);
    hideLoading();
    
    if (e.message.includes("Invalid JSON")) {
      addMsg("서버 응답 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.");
    } else if (e.message.includes("HTTP")) {
      addMsg("서버 연결에 문제가 있습니다. 네트워크 상태를 확인해 주세요.");
    } else {
      addMsg("수정에 실패했습니다. 다시 시도해 주세요.");
    }
  }
}

/** 피드백(자연어)로 일정 수정 - 기존 함수 유지 */
async function reviseScheduleWithFeedback(feedback) {
  if (!feedback) return;
  addMsg(feedback, true);
  try {
    const sched = await sendScheduleFeedback(feedback);
    addMsg("요청하신 내용으로 일정을 수정했어요.");
    renderTableFromSchedule(sched);
    updateHomeCalendar();
    renderHomeTimeline();
  } catch (e) {
    console.error("일정 수정 에러:", e);
    
    if (e.message.includes("Invalid JSON")) {
      alert("서버 응답 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.");
    } else if (e.message.includes("HTTP")) {
      alert("서버 연결에 문제가 있습니다. 네트워크 상태를 확인해 주세요.");
    } else {
      alert("수정에 실패했습니다. 다시 시도해 주세요.");
    }
  }
}

/** 일정 확정 → 채팅 내 미니 캘린더 + 홈 동기화 */
async function confirmCurrentSchedule() {
  const btn = $("#confirm");
  btn.disabled = true;
  const old = btn.textContent;
  btn.textContent = "확정 중…";
  try {
    await confirmSchedule();
    addMsg("일정을 확정했어요. 홈 화면의 캘린더에서 확인하실 수 있습니다!");
    updateHomeCalendar();
    
    // 일정 확정 후 홈 화면으로 즉시 이동
    STATE.tab = "home";
    render();
    
  } catch (e) {
    console.error(e);
    alert("확정에 실패했습니다.");
  } finally {
    btn.disabled = false;
    btn.textContent = old;
  }
}

/** 메인 렌더 */
function renderChat() {
  const c = $(".container");
  const seed = localStorage.getItem("ims_home_query") || "";
  
  // 기존 채팅 내용이 있는지 확인
  const existingChat = $("#chat");
  let chatContent = "";
  
  if (!existingChat) {
    // 처음 렌더링할 때만 초기 메시지 추가
    chatContent = `
      <div class="msg bot">언제 어디로 떠날 계획이신가요?</div>
      ${seed ? `<div class="msg me">${seed}</div>` : ""}
    `;
  } else {
    // 기존 채팅 내용 보존
    chatContent = existingChat.innerHTML;
  }

  c.innerHTML = `
    <div class="card">
      <div class="section-title">일여행 계획하기</div>
      <div class="chat" id="chat">
        ${chatContent}
      </div>

      <div id="cardsWrap"></div>
      <div id="pickedWrap"></div>
      <div id="tableWrap"></div>

      <div class="inputbar">
        <input class="input" id="chatInput" placeholder="원하는 조건을 말해보세요 (예: 전주 당일치기)">
        <button class="btn" id="send">▶</button>
      </div>
      <div style="display:flex; gap:8px; margin-top:8px">
        <button class="btn secondary" id="confirm">일정 확정</button>
        <button class="btn ghost" id="homeBack">홈</button>
      </div>
    </div>`;

  $("#homeBack").onclick = () => navigate("home");
  $("#confirm").onclick = confirmCurrentSchedule;

  // 채팅 전송 - 상황에 따라 다르게 처리
  $("#send").onclick = async () => {
    const text = $("#chatInput").value.trim();
    if (!text) return;
    $("#chatInput").value = "";
    
    // 타임테이블이 이미 생성된 상태라면 피드백으로 처리
    if (STATE.chatStage === "table" && STATE.last_schedule) {
      await handleScheduleFeedback(text);
    } else {
      // 새로운 추천 요청
      await triggerRecommendation(text);
    }
  };

  // 홈에서 넘어온 쿼리가 있으면 자동 실행 (사용자 메시지는 이미 표시되어 있으므로 스킵)
  const homeQuery = localStorage.getItem("ims_home_query");
  if (homeQuery && seed) {
    localStorage.removeItem("ims_home_query"); // 한 번만 실행
    setTimeout(() => {
      // 채팅 입력창 초기화 후 추천 호출
      if ($("#chatInput")) {
        $("#chatInput").value = "";
      }
      triggerRecommendation(seed, true); // skipUserMessage = true
    }, 500);
  }
}

function renderOnboard() {
  const container = $(".container");
  container.innerHTML = `
    <div class="steps-indicator">1/5</div>
    <div class="card">
      <!-- 타이틀 줄바꿈 -->
      <div class="h1">새롭게 떠나고픈 당신,<br>일멍쉬멍 프로필을 만들어 볼까요?</div>

      <!-- 닉네임 -->
      <input class="input mb-12" id="nick" placeholder="닉네임" />

      <!-- 거주지 라벨 -->
      <div class="form-label mt-12">거주지</div>
      <div class="grid grid-2 mb-12">
        <select id="sido">
          <option value="">시/도</option>
          ${[
            "서울",
            "부산",
            "대전",
            "대구",
            "광주",
            "울산",
            "세종",
            "경기",
            "강원",
            "충북",
            "충남",
            "전북",
            "전남",
            "경북",
            "경남",
            "제주",
          ]
            .map((s) => `<option>${s}</option>`)
            .join("")}
        </select>
        <input class="input" id="sigungu" placeholder="시/군/구" />
      </div>

      <!-- 나이 -->
      <input class="input mb-12" id="age" placeholder="나이" />

      <!-- 성별 -->
      <div class="form-label">성별</div>
      <div class="radio-row">
        <label><input type="radio" name="gender" value="M"> 남</label>
        <label><input type="radio" name="gender" value="F"> 여</label>
      </div>

      <div class="section-title">누구와 떠날까요?</div>
      <div class="badges" id="withWho">
        ${["혼자", "친구와", "연인과", "배우자와", "부모님과", "기타"]
          .map((s) => `<button class="badge">${s}</button>`)
          .join("")}
      </div>

      <div style="height:12px"></div>
      <button class="btn btn-lg" id="next1">다음</button>
    </div>
  `;

  setupBadgeToggle(
    "withWho",
    () => STATE.profile.with || [],
    (values) => {
      STATE.profile.with = values;
      saveState();
    }
  );

  $("#next1").onclick = () => {
    STATE.profile.nick = $("#nick").value;
    STATE.profile.region = {
      sido: $("#sido").value,
      sigungu: $("#sigungu").value,
    };
    STATE.profile.age = $("#age").value;
    STATE.profile.gender =
      ($('input[name="gender"]:checked') || {}).value || "";
    STATE.profile.with = Array.from($$("#withWho .badge.active")).map((b) =>
      b.textContent.trim()
    );
    saveState();
    navigate("onboard2");
  };
}

function renderOnboard2() {
  const container = $(".container");
  const rows = [
    { label: "산", desc: "능선 트레킹 · 계곡 물놀이" },
    { label: "바다", desc: "해수욕 · 해산물 · 서핑" },
    { label: "강·호수", desc: "카약 · 자전거 라이딩" },
    { label: "숲", desc: "치유 트레킹 · 캠핑" },
    { label: "섬", desc: "낚시 · 섬마을 체험" },
  ];
  container.innerHTML = `
    <div class="steps-indicator">2/5</div>
    <div class="card">
      <div class="step-hero">
        <img src="./assets/icons/landscape.png" alt="풍경 아이콘">
      </div>
      <div class="h1">어떤 풍경을 좋아하시나요?</div>
      <div class="sub">유사한 자연환경을 우선으로 추천해드릴게요.</div>

      <div class="list-rows" id="sceneRows">
        ${rows
          .map(
            (r) => `
          <div class="row">
            <button class="badge">${r.label}</button>
            <div class="desc">${r.desc}</div>
          </div>`
          )
          .join("")}
      </div>

      <button class="btn btn-lg" id="next2">다음</button>
    </div>
  `;
  setupBadgeToggle(
    "sceneRows",
    () => STATE.prefs.scenery || [],
    (v) => {
      STATE.prefs.scenery = v;
      saveState();
    }
  );
  $("#next2").onclick = () => navigate("onboard3");
}

function renderOnboard3() {
  const container = $(".container");
  const rows = [
    { label: "힐링·여유", desc: "온천 · 전망대 · 카페" },
    { label: "체험형", desc: "로컬푸드 쿠킹 · 전통 공예" },
    { label: "야외활동", desc: "트레킹 · MTB · 캠핑" },
    { label: "레저·액티비티", desc: "서핑 · 래프팅 · 패러글라이딩" },
    { label: "문화·역사", desc: "유적 · 박물관 · 전통시장" },
    { label: "축제·이벤트", desc: "불꽃놀이 · 지역 축제" },
    { label: "먹거리 탐방", desc: "시장 투어 · 미식" },
    { label: "사진 스팟", desc: "일출 · 일몰 · SNS 핫플" },
  ];
  container.innerHTML = `
    <div class="steps-indicator">3/5</div>
    <div class="card">
      <div class="step-hero">
        <img src="./assets/icons/camera.png" alt="스타일 아이콘">
      </div>
      <div class="h1">내가 선호하는 여행 스타일은?</div>
      <div class="sub">유사한 활동을 우선으로 추천해드릴게요.</div>

      <div class="list-rows" id="styleRows">
        ${rows
          .map(
            (r) => `
          <div class="row">
            <button class="badge">${r.label}</button>
            <div class="desc">${r.desc}</div>
          </div>`
          )
          .join("")}
      </div>

      <button class="btn btn-lg" id="next3">다음</button>
    </div>
  `;
  setupBadgeToggle(
    "styleRows",
    () => STATE.prefs.styles || [],
    (v) => {
      STATE.prefs.styles = v;
      saveState();
    }
  );
  $("#next3").onclick = () => navigate("onboard4");
}

function renderOnboard4() {
  const container = $(".container");
  const rows = [
    { label: "채소", desc: "상추 · 고추 모종 심기" },
    { label: "과수", desc: "사과 · 배 따기 체험" },
    { label: "화훼", desc: "꽃 모종 옮겨심기" },
    { label: "식량작물", desc: "벼 모내기 · 수확 체험" },
    { label: "축산", desc: "동물 돌봄 체험(송아지, 닭 등)" },
    { label: "농기계", desc: "농기계 안전 교육 및 관리 체험" },
  ];
  container.innerHTML = `
    <div class="steps-indicator">4/5</div>
    <div class="card">
      <div class="step-hero">
        <img src="./assets/icons/farm.png" alt="체험/일자리 아이콘">
      </div>
      <div class="h1">원하시는 체험·일자리를 알려주세요.</div>
      <div class="sub">유사한 체험과 일손 돕기를 우선으로 추천해드릴게요.</div>

      <div class="list-rows" id="jobRows">
        ${rows
          .map(
            (r) => `
          <div class="row">
            <button class="badge">${r.label}</button>
            <div class="desc">${r.desc}</div>
          </div>`
          )
          .join("")}
      </div>

      <button class="btn btn-lg" id="next4">다음</button>
    </div>
  `;
  setupBadgeToggle(
    "jobRows",
    () => STATE.prefs.jobs || [],
    (v) => {
      STATE.prefs.jobs = v;
      saveState();
    }
  );
  $("#next4").onclick = () => navigate("onboard5");
}

function renderOnboard5() {
  const container = $(".container");
  container.innerHTML = `
    <div class="steps-indicator">5/5</div>
    <div class="card">
      <div class="step-hero">
        <img src="./assets/icons/search.png" alt="완료 아이콘">
      </div>
      <div class="h1">어떤 여행을 선호하시나요?</div>
      <div class="sub">자유롭게 적어주세요!</div>

      <input class="input mb-12" id="free1" placeholder="활동 1 (ex. 뚜벅이 여행)">
      <input class="input mb-12" id="free2" placeholder="활동 2 (ex. 자연 산책)">
      <input class="input mb-12" id="free3" placeholder="활동 3 (ex. 사진 스팟)">
      <input class="input mb-12" id="free4" placeholder="활동 4 (ex. 숨겨진 맛집)">
      <input class="input mb-12" id="free5" placeholder="활동 5 (ex. 빵, 디저트 투어)">

      <button class="btn btn-lg" id="finish">완료</button>
    </div>
  `;
  $("#finish").onclick = async (e) => {
    const btn = e.currentTarget;
    STATE.prefs.free = [1, 2, 3, 4, 5]
      .map((i) => $("#free" + i).value)
      .filter(Boolean);
    saveState();

    const label = btn.textContent;
    btn.disabled = true;
    btn.textContent = "완료 · 전송중…";
    try {
      await sendOnboardingAndGetUserId(); // ✅ 여기서 user_id 발급
      navigate("home");
    } catch (err) {
      console.error(err);
      alert(
        "프로필 전송에 실패했습니다. 네트워크/주소를 확인 후 다시 시도해주세요."
      );
      btn.disabled = false;
      btn.textContent = label;
    }
  };
}

function render() {
  renderHeader();
  const map = {
    onboard: renderOnboard,
    onboard2: renderOnboard2,
    onboard3: renderOnboard3,
    onboard4: renderOnboard4,
    onboard5: renderOnboard5,
    home: renderHome,
    chat: renderChat,
  };
  (map[STATE.view] || renderHome)();
}
document.addEventListener("DOMContentLoaded", () => {
  if ("serviceWorker" in navigator)
    navigator.serviceWorker.register("./service-worker.js");
  render();
});
