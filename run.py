"""主程式。用法：python run.py full | core | test
full：掃全部帳戶，發「結論總表＋成本線圖」，同時檢查警報。
core：只掃贏家與輸家（歷史盈虧超過 ±10 萬美元），有警報才發。
test：小樣本快速測試，會發一則標示「測試」的訊息，不寫入歷史。
環境變數 DISCORD_WEBHOOK：Discord 發送網址（沒有設定時只把圖存到 out/）。
"""
import csv, datetime as dt, json, os, sys, time
from zoneinfo import ZoneInfo
import requests
import hl, charts
from charts import side

MODE = sys.argv[1] if len(sys.argv) > 1 else "test"
TPE = ZoneInfo("Asia/Taipei")
NOW = dt.datetime.now(TPE)
STAMP = NOW.strftime("%Y-%m-%d %H:%M")
WEBHOOK = os.environ.get("DISCORD_WEBHOOK", "").strip()
STATE_F, HIST_F, COST_F, OC = "data/state.json", "data/history.csv", "data/cost_history.csv", "data/onchain"
BIG_MOVE, MIN_PEOPLE, NEAR_PCT = 15, 30, 5   # 警報門檻：變動百分點、最少人數、接近成本線的距離 %
os.makedirs("out", exist_ok=True); os.makedirs(OC, exist_ok=True)


# ------------------------------------------------------------ Discord
def post(text, files=()):
    print("=== MESSAGE ===\n" + text + "\nfiles:", [f for f, _ in files], flush=True)
    if not WEBHOOK:
        print("(未設定 DISCORD_WEBHOOK，只存檔不發送)"); return
    fs = {f"files[{i}]": (name, open(path, "rb"), "image/png") for i, (path, name) in enumerate(files)}
    for attempt in range(4):
        try:
            r = requests.post(WEBHOOK, data={"payload_json": json.dumps({"content": text[:1900]})}, files=fs or None, timeout=120)
            if r.status_code in (200, 204): print("discord ok"); return
            print("discord status", r.status_code, r.text[:200])
            if r.status_code == 429: time.sleep(float(r.json().get("retry_after", 5)) + 1)
        except Exception as e:  # noqa
            print("discord error", repr(e)[:200])
        for f in fs.values(): f[1].seek(0)
        time.sleep(5)
    raise SystemExit("Discord 發送失敗")


# ------------------------------------------------------------ 鏈上成本資料（每天最多更新一次，失敗就用舊檔）
def load_series(name, key):
    try:
        return {r["d"]: float(r[key]) for r in json.load(open(f"{OC}/{name}.json")) if r.get(key) not in (None, "")}
    except Exception:
        return {}


def refresh_onchain():
    meta_f = f"{OC}/meta.json"
    try: meta = json.load(open(meta_f))
    except Exception: meta = {}
    today = NOW.strftime("%Y-%m-%d")
    if meta.get("fetched") == today or MODE == "test": return
    ok = True
    for name, ep in (("lth", "lth-realized-price"), ("sth", "sth-realized-price"), ("price", "btc-price")):
        try:
            r = requests.get(f"https://bitcoin-data.com/v1/{ep}", timeout=90)
            data = r.json()
            if r.status_code == 200 and isinstance(data, list) and len(data) > 500:
                json.dump(data, open(f"{OC}/{name}.json", "w"))
            else:
                ok = False; print("onchain", ep, "unexpected", r.status_code, str(data)[:150])
        except Exception as e:  # noqa
            ok = False; print("onchain", ep, "error", repr(e)[:150])
        time.sleep(3)
    if ok: json.dump({"fetched": today}, open(meta_f, "w"))


def cost_block(now_price, make_chart):
    P, L, S = load_series("price", "btcPrice"), load_series("lth", "lthRealizedPrice"), load_series("sth", "sthRealizedPrice")
    if not (P and L and S): return None
    try:
        if make_chart: return charts.draw_cost(P, L, S, now_price, STAMP, "out/06_cost.png")
        return charts.cost_info(P, L, S, now_price)
    except Exception as e:  # noqa
        print("cost chart error", repr(e)[:300]); return None


# ------------------------------------------------------------ 判讀
def judge(res, core_only):
    w, l = res["win"], res["lose"]
    reasons = []
    if min(w["people"], l["people"]) < 50: reasons.append("人數少")
    if max(w["topshare"], l["topshare"]) > 30: reasons.append("單一大戶佔比高")
    opp = lambda d: {side(d["amt"]), side(d["cnt"])} == {"多", "空"}
    if opp(w) or opp(l): reasons.append("人數與金額方向相反")
    conf = ["高", "中", "低", "低"][len(reasons)]
    a, b = side(w["amt"]), side(l["amt"])
    if "無" in (a, b): verdict = "資料不足"
    elif a == "空" and b == "多": verdict = "贏家偏空，輸家偏多"
    elif a == "多" and b == "空": verdict = "贏家偏多，輸家偏空"
    elif a == b == "多": verdict = "贏家輸家都偏多"
    elif a == b == "空": verdict = "贏家輸家都偏空"
    elif a == "平": verdict = "贏家沒有明顯方向"
    else: verdict = f"贏家偏{a}，輸家沒有明顯方向"
    return dict(conf=conf, reasons=reasons, verdict=verdict, a=a, b=b)


def headline(rows):
    coins = [r for r in rows[1:] if r["conf"] != "低"]
    if not coins: return "各幣種樣本不足，這次沒有可信的結論"
    opp = [r["name"] for r in coins if r["a"] == "空" and r["b"] == "多"]
    opp2 = [r["name"] for r in coins if r["a"] == "多" and r["b"] == "空"]
    if opp and len(opp) >= len(opp2): return f"{len(coins)} 個幣種中有 {len(opp)} 個「贏家偏空、輸家偏多」：" + "、".join(opp)
    if opp2: return f"{len(coins)} 個幣種中有 {len(opp2)} 個「贏家偏多、輸家偏空」：" + "、".join(opp2)
    both = [r["name"] for r in coins if r["a"] == r["b"] and r["a"] in ("多", "空")]
    if both: return "贏家與輸家站同一邊：" + "、".join(f"{r['name']}（都偏{r['a']}）" for r in coins if r["name"] in both)
    return "目前贏家與輸家沒有明顯對立"


# ------------------------------------------------------------ 警報
CLS_NAME = {"win": "贏家", "lose": "輸家"}


def check_alerts(rows, cost, state, full):
    alerts, coins_hit = [], []
    sides, last = state.setdefault("sides", {}), state.setdefault("last", {})
    first = not last
    for r in rows:
        for cls in ("win", "lose"):
            d = r["res"][cls]; p = d["amt"]
            if p is None or d["people"] < MIN_PEOPLE: continue
            key = f"{r['name']}|{cls}"
            prev_side, prev_val = sides.get(key), last.get(key)
            new_side = "多" if p >= 55 else "空" if p <= 45 else (prev_side or "平")
            who = f"{r['name']} {CLS_NAME[cls]}"
            if prev_side in ("多", "空") and new_side in ("多", "空") and new_side != prev_side:
                alerts.append(f"轉向：{who}由偏{prev_side}轉為偏{new_side}（偏多比例 {prev_val:.0f}% → {p:.0f}%）"); coins_hit.append(r)
            elif prev_val is not None and abs(p - prev_val) >= BIG_MOVE:
                alerts.append(f"大變動：{who}偏多比例 {prev_val:.0f}% → {p:.0f}%（{p - prev_val:+.0f} 個百分點）"); coins_hit.append(r)
            sides[key], last[key] = new_side, p
        if full:
            pc = state.setdefault("conf", {}).get(r["name"])
            if pc and pc != r["conf"]:
                alerts.append(f"可信度改變：{r['name']} 由「{pc}」變為「{r['conf']}」" + (f"（{'、'.join(r['reasons'])}）" if r["reasons"] else ""))
            state["conf"][r["name"]] = r["conf"]
    cost_alert = False
    if cost:
        cs = state.setdefault("cost", {})
        if cs.get("zone") and cs["zone"] != cost["zone"]:
            alerts.append(f"長線位置改變：由「{charts.ZNAME[cs['zone']]}」進入「{charts.ZNAME[cost['zone']]}」（價格 ${cost['price']:,.0f}，長期持有者成本 ${cost['lth']:,.0f}）"); cost_alert = True
        near = abs(cost["gap"]) < NEAR_PCT
        if near and not cs.get("near"):
            alerts.append(f"接近成本線：價格距離長期持有者成本只剩 {abs(cost['gap']):.1f}%"); cost_alert = True
        cs["zone"] = cost["zone"]
        cs["near"] = near if abs(cost["gap"]) < NEAR_PCT + 2 else False
    if first: alerts = []   # 第一次執行沒有比較基準，不發警報
    seen, uniq = set(), []
    for r in coins_hit:
        if r["name"] not in seen: seen.add(r["name"]); uniq.append(r)
    return alerts, uniq, cost_alert


# ------------------------------------------------------------ 主流程
def main():
    full = MODE in ("full", "test")
    groups = "ABCDEF" if full else "ABEF"
    recs, total, ok = hl.scan(groups, limit=300 if MODE == "test" else 0)
    if total == 0 or ok / total < 0.9:
        msg = f"【系統通知】{STAMP} 資料抓取不完整（成功 {ok}/{total}），這次不發報告，下次排程會自動重試。"
        if MODE != "core": post(msg)
        raise SystemExit(msg)
    try: price = hl.btc_price()
    except Exception: price = None
    refresh_onchain()

    rows = []
    for coin, name in hl.COINS:
        res = hl.agg_classes(recs, coin)
        rows.append(dict(coin=coin, name=name, res=res, **judge(res, not full)))
    order = {"高": 0, "中": 1, "低": 2}
    rows = [rows[0]] + sorted(rows[1:], key=lambda r: order[r["conf"]])
    head = headline(rows)
    cost = cost_block(price, make_chart=True) if price else None

    try: state = json.load(open(STATE_F))
    except Exception: state = {}
    if MODE == "test":
        alerts, hit, cost_alert = [], [], False
    else:
        alerts, hit, cost_alert = check_alerts(rows, cost, state, full)

    tag = "（測試）" if MODE == "test" else ("" if full else "（警報快照）")
    charts.draw_summary(rows, head, STAMP, cost, "out/00_summary.png", core_only=not full, tag=tag)
    files = [("out/00_summary.png", "00_summary.png")]
    cost_line = ""
    if cost:
        cost_line = (f"長線位置：價格比長期持有者成本高 {cost['gap']:.0f}%（{charts.ZNAME[cost['zone']]}），再跌 {cost['drop']:.0f}% 會跌破"
                     if cost["gap"] >= 0 else f"長線位置：價格比長期持有者成本低 {abs(cost['gap']):.0f}%（已跌破，{charts.ZNAME[cost['zone']]}）")

    if full:
        if cost: files.append(("out/06_cost.png", "06_cost.png"))
        for i, r in enumerate(hit[:3], 1):
            fn = f"out/detail_{r['name']}.png"
            charts.draw_detail(recs, r["coin"], f"細節圖｜{r['name']}（可信度{r['conf']}）", STAMP, fn)
            files.append((fn, f"detail_{i}.png"))
        label = "測試報告" if MODE == "test" else ("早報" if NOW.hour < 14 else "晚報")
        text = f"**多空比{label}** {STAMP}\n{head}\n{cost_line}"
        if alerts: text += "\n\n**【警報】**\n" + "\n".join("・" + a for a in alerts)
        if MODE == "test": text += "\n（這是小樣本測試，數字不具參考性，只用來確認系統能正常發送。）"
        post(text, files)
    elif alerts:
        if cost_alert and cost: files.append(("out/06_cost.png", "06_cost.png"))
        post(f"**【警報】** {STAMP}\n" + "\n".join("・" + a for a in alerts) + f"\n\n{cost_line}\n（警報快照只更新贏家與輸家，完整報告請看早晚報）", files)
    else:
        print("core check: 沒有警報，不發送")

    if MODE != "test":
        state["last_time"] = STAMP
        json.dump(state, open(STATE_F, "w"), ensure_ascii=False, indent=1)
        new = not os.path.exists(HIST_F)
        with open(HIST_F, "a", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            if new: w.writerow(["time", "mode", "coin", "class", "amt_long_pct", "cnt_long_pct", "people", "value_usd", "top1_share_pct", "confidence"])
            for r in rows:
                for cls in (("win", "mid", "lose") if full else ("win", "lose")):
                    d = r["res"][cls]
                    w.writerow([STAMP, MODE, r["name"], cls, d["amt"], d["cnt"], d["people"], d["value"], d["topshare"], r["conf"] if full else ""])
        if cost:
            new = not os.path.exists(COST_F)
            with open(COST_F, "a", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                if new: w.writerow(["time", "price", "lth_cost", "sth_cost", "gap_pct", "zone", "cost_data_date"])
                w.writerow([STAMP, round(cost["price"]), cost["lth"], cost["sth"], round(cost["gap"], 2), cost["zone"], cost["lth_date"]])


if __name__ == "__main__":
    main()
