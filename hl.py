"""Hyperliquid 資料：下載排行榜、掃描各帳戶持倉、依歷史總盈虧分群彙總。"""
import random, threading, time
from concurrent.futures import ThreadPoolExecutor
import requests

INFO = "https://api.hyperliquid.xyz/info"
LEADERBOARD = "https://stats-data.hyperliquid.xyz/Mainnet/leaderboard"
RATE = 9.5  # 每秒請求數（官方上限：每分鐘 1200 權重，查持倉每次權重 2）

GROUPS = [("A", "極度獲利", "賺超過 100 萬美元"), ("B", "非常獲利", "賺 10 萬～100 萬"),
          ("C", "獲利", "賺 0～10 萬"), ("D", "虧損", "賠 0～10 萬"),
          ("E", "嚴重虧損", "賠 10 萬～100 萬"), ("F", "極度虧損", "賠超過 100 萬美元")]
CLASS_OF = {"A": "win", "B": "win", "C": "mid", "D": "mid", "E": "lose", "F": "lose"}
COINS = [(None, "全幣種"), ("BTC", "BTC"), ("ETH", "ETH"), ("SOL", "SOL"), ("HYPE", "HYPE")]


def group_of(pnl):
    if pnl > 1e6: return "A"
    if pnl > 1e5: return "B"
    if pnl >= 0: return "C"
    if pnl > -1e5: return "D"
    if pnl > -1e6: return "E"
    return "F"


def fetch_leaderboard():
    for attempt in range(4):
        try:
            r = requests.get(LEADERBOARD, timeout=300)
            r.raise_for_status()
            rows = r.json()["leaderboardRows"]
            out = []
            for row in rows:
                pnl = next(float(v["pnl"]) for k, v in row["windowPerformances"] if k == "allTime")
                out.append((row["ethAddress"], pnl, group_of(pnl)))
            return out
        except Exception as e:  # noqa
            print("leaderboard retry", attempt, repr(e)[:120], flush=True)
            time.sleep(10 * (attempt + 1))
    raise RuntimeError("無法下載 Hyperliquid 排行榜")


def btc_price():
    r = requests.post(INFO, json={"type": "allMids"}, timeout=30)
    r.raise_for_status()
    return float(r.json()["BTC"])


def scan(groups, limit=0):
    """掃描指定群組的所有帳戶。回傳 (records, 目標數, 成功數)。
    record = {"a": 地址, "pnl": 歷史盈虧, "g": 群組, "pos": [[幣, 數量(正多負空), 倉位金額], ...]}"""
    todo = [t for t in fetch_leaderboard() if t[2] in groups]
    if limit:
        random.seed(1)
        per = max(1, limit // len(groups))
        picked = []
        for g in groups:
            lst = [t for t in todo if t[2] == g]
            picked += random.sample(lst, min(per, len(lst)))
        todo = picked
    print("to scan:", len(todo), flush=True)
    lock = threading.Lock()
    next_t = [time.time()]
    local = threading.local()
    recs = []

    def wait_slot():
        with lock:
            now = time.time()
            t = max(now, next_t[0])
            next_t[0] = t + 1.0 / RATE
        time.sleep(max(0, t - now))

    def fetch(item):
        a, pnl, g = item
        if not hasattr(local, "s"): local.s = requests.Session()
        for attempt in range(7):
            wait_slot()
            try:
                r = local.s.post(INFO, json={"type": "clearinghouseState", "user": a}, timeout=20)
                if r.status_code == 200:
                    pos = [[x["position"]["coin"], float(x["position"]["szi"]), float(x["position"]["positionValue"])]
                           for x in r.json().get("assetPositions", [])]
                    with lock: recs.append({"a": a, "pnl": pnl, "g": g, "pos": pos})
                    return True
                if r.status_code == 429:
                    with lock: next_t[0] = max(next_t[0], time.time()) + 8
            except Exception:
                pass
            time.sleep(1 + attempt)
        return False

    t0 = time.time(); ok = 0
    with ThreadPoolExecutor(12) as ex:
        for i, res in enumerate(ex.map(fetch, todo), 1):
            ok += bool(res)
            if i % 2000 == 0: print(i, "/", len(todo), "ok", ok, round(time.time() - t0), "s", flush=True)
    print("scan done ok", ok, "of", len(todo), round(time.time() - t0), "s", flush=True)
    return recs, len(todo), ok


def agg_groups(recs, coin):
    """6 群明細：{群: nl 偏多人數, ns 偏空人數, vl 多單金額, vs 空單金額}"""
    res = {g: dict(nl=0, ns=0, vl=0.0, vs=0.0) for g, _, _ in GROUPS}
    for r in recs:
        pos = r["pos"] if coin is None else [p for p in r["pos"] if p[0] == coin]
        if not pos: continue
        d = res[r["g"]]; net = 0.0
        for _, szi, val in pos:
            if szi > 0: d["vl"] += val; net += val
            elif szi < 0: d["vs"] += val; net -= val
        if net > 0: d["nl"] += 1
        elif net < 0: d["ns"] += 1
    return res


def agg_classes(recs, coin):
    """3 類彙總（贏家/一般戶/輸家）：amt 金額偏多%、cnt 人數偏多%、people 人數、topshare 最大單一帳戶佔比%"""
    res = {c: dict(nl=0, ns=0, vl=0.0, vs=0.0, top=0.0) for c in ("win", "mid", "lose")}
    for r in recs:
        pos = r["pos"] if coin is None else [p for p in r["pos"] if p[0] == coin]
        if not pos: continue
        d = res[CLASS_OF[r["g"]]]
        l = sum(v for _, s, v in pos if s > 0); s_ = sum(v for _, s, v in pos if s < 0)
        d["vl"] += l; d["vs"] += s_; d["top"] = max(d["top"], l + s_)
        if l > s_: d["nl"] += 1
        elif s_ > l: d["ns"] += 1
    out = {}
    for c, d in res.items():
        v = d["vl"] + d["vs"]; n = d["nl"] + d["ns"]
        out[c] = dict(amt=round(100 * d["vl"] / v, 2) if v else None, cnt=round(100 * d["nl"] / n, 2) if n else None,
                      people=n, value=round(v), topshare=round(100 * d["top"] / v, 1) if v else 0)
    return out
