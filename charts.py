"""三種圖：結論總表、多空比細節圖、長線位置（成本線）圖。"""
import datetime as dt, math
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib import font_manager as fm
from matplotlib.ticker import FuncFormatter
from matplotlib.collections import LineCollection
from matplotlib.patches import FancyBboxPatch
from hl import GROUPS, agg_groups

FONT = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"
FONTB = "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"
fp = lambda s: fm.FontProperties(fname=FONT, size=s)
fpb = lambda s: fm.FontProperties(fname=FONTB, size=s)
LONG, SHORT, GRAY = "#2a78d6", "#d6453d", "#8a8985"
LONG_DIM, SHORT_DIM = "#bcd3ef", "#f1c3bf"
SURF, INK, INK2, GRID, BOX = "#fcfcfb", "#0b0b0b", "#52514e", "#e3e2de", "#f0efec"
AMB = "#c98500"
DOT = "#1f5fbf"
ZB, ZA, ZR = "#dce8f8", "#f8ecd0", "#f6d6d3"
ZNAME = {"strong": "強勢區", "mid": "中間區", "bear": "熊底區"}


def side(p):
    if p is None: return "無"
    return "多" if p >= 55 else "空" if p <= 45 else "平"


def money(v):
    if v >= 1e9: return f"\\${v/1e9:.2f}B"
    if v >= 1e6: return f"\\${v/1e6:.1f}M"
    return f"\\${v/1e3:.0f}K"


# ---------------------------------------------------------------- 結論總表
def draw_summary(rows, head, stamp, cost, fname, core_only=False, tag=""):
    n = len(rows)
    H = 48 + 15.5 * n
    fig = plt.figure(figsize=(9, H / 10), facecolor=SURF)
    ax = fig.add_axes([0, 0, 1, 1]); ax.set_xlim(0, 100); ax.set_ylim(0, H); ax.axis("off")
    ax.text(4, H - 4.5, f"00 結論總表｜贏家 vs 輸家{tag}", fontproperties=fpb(22), color=INK, va="center")
    ax.text(4, H - 9, f"Hyperliquid・按倉位金額・快照 {stamp}（台北）", fontproperties=fp(11), color=INK2, va="center")
    ax.add_patch(FancyBboxPatch((4, H - 18.2), 92, 6.2, boxstyle="round,pad=0,rounding_size=1.2", fc=BOX, ec="none"))
    ax.text(6, H - 15.1, head, fontproperties=fpb(13), color=INK, va="center")
    # 長線位置
    ax.add_patch(FancyBboxPatch((4, H - 29.5), 92, 9.3, boxstyle="round,pad=0,rounding_size=1.2", fc=BOX, ec="none"))
    ax.text(6, H - 22.6, "長線位置（BTC）", fontproperties=fpb(11), color=INK2, va="center")
    if cost:
        g = cost["gap"]
        l1 = (f"價格比長期持有者成本高 {g:.0f}%，在「{ZNAME[cost['zone']]}」" if g >= 0
              else f"價格比長期持有者成本低 {abs(g):.0f}%（已跌破），在「{ZNAME[cost['zone']]}」")
        l2 = (f"再跌 {cost['drop']:.0f}% 會跌破成本線 \\${cost['lth']:,.0f}" if g >= 0 else f"長期持有者成本 \\${cost['lth']:,.0f}")
        ax.text(30, H - 22.6, l1, fontproperties=fpb(12.5), color=INK, va="center")
        ax.text(30, H - 26.6, l2 + f"　目前價格 \\${cost['price']:,.0f}", fontproperties=fp(11), color=INK, va="center")
    else:
        ax.text(30, H - 24.6, "成本線資料暫時無法取得", fontproperties=fp(11.5), color=INK2, va="center")
    X = [4, 22, 42, 62, 84]
    for x, t in zip(X, ["幣種", "贏家\n賺超過 10 萬美元", "一般戶\n賺賠 10 萬以內", "輸家\n賠超過 10 萬美元", "可信度"]):
        ax.text(x, H - 34.5, t, fontproperties=fpb(10.5), color=INK2, va="center", linespacing=1.35)
    y = H - 39
    COL = {"多": LONG, "空": SHORT, "平": GRAY, "無": "#d9d8d4"}
    CONFCOL = {"高": INK, "中": INK2, "低": GRAY}
    for r in rows:
        ax.plot([4, 96], [y, y], color=GRID, lw=1)
        yc = y - 6
        ax.text(X[0], yc + 1.2, r["name"], fontproperties=fpb(17), color=INK, va="center")
        for x, k in zip(X[1:4], ["win", "mid", "lose"]):
            d = r["res"][k]; p = d["amt"]; sd = side(p)
            if core_only and k == "mid": sd, txt = "無", "本次未更新"
            elif sd == "無": txt = "無持倉"
            else: txt = f"偏多 {p:.0f}%" if sd == "多" else f"偏空 {100-p:.0f}%" if sd == "空" else f"持平 多{p:.0f}%"
            ax.add_patch(FancyBboxPatch((x, yc - 0.9), 16.5, 4.6, boxstyle="round,pad=0,rounding_size=1.1", fc=COL[sd], ec="none"))
            ax.text(x + 8.25, yc + 1.4, txt, fontproperties=fpb(13 if sd != "無" else 11), color="white" if sd != "無" else INK2, va="center", ha="center")
            if sd != "無":
                ax.text(x + 8.25, yc - 3, f"{d['people']:,} 人", fontproperties=fp(9), color=INK2, va="center", ha="center")
        ax.text(X[4], yc + 1.4, r["conf"], fontproperties=fpb(18), color=CONFCOL[r["conf"]], va="center")
        if r["reasons"]:
            ax.text(X[4], yc - 3, "\n".join(r["reasons"]), fontproperties=fp(8.5), color=INK2, va="center", linespacing=1.3)
        ax.text(X[0], yc - 7.3, "→ " + r["verdict"], fontproperties=fp(11.5), color=INK, va="center")
        y -= 15.5
    ax.plot([4, 96], [y, y], color=GRID, lw=1)
    ax.text(4, 3.6, "藍＝偏多　紅＝偏空　灰＝持平（45%～55%）。只描述各群站哪一邊，不是買賣建議。\n範圍：Hyperliquid 排行榜帳戶的主站永續合約持倉；人數為有持倉的帳戶數。",
            fontproperties=fp(8.8), color=INK2, va="center", linespacing=1.5)
    fig.savefig(fname, dpi=150, facecolor=SURF); plt.close(fig)


# ---------------------------------------------------------------- 多空比細節圖
def _panel(ax, res, mode, title):
    ax.set_facecolor(SURF)
    ys = list(range(len(GROUPS)))[::-1]
    for y, (g, name, rng) in zip(ys, GROUPS):
        d = res[g]
        l, s = (d["nl"], d["ns"]) if mode == "n" else (d["vl"], d["vs"])
        tot = l + s
        ax.text(-108, y + 0.13, name, ha="right", va="center", color=INK, fontproperties=fpb(12))
        ax.text(-108, y - 0.2, rng, ha="right", va="center", color=INK2, fontproperties=fp(9.5))
        if tot == 0:
            ax.text(0, y, "無資料", ha="center", va="center", fontproperties=fp(11), color=INK2); continue
        pl, ps = 100 * l / tot, 100 * s / tot
        win_long = pl >= ps
        ax.barh(y, -ps, height=0.62, color=SHORT if not win_long else SHORT_DIM, left=-0.4, linewidth=0)
        ax.barh(y, pl, height=0.62, color=LONG if win_long else LONG_DIM, left=0.4, linewidth=0)
        for p, sign, win in ((ps, -1, not win_long), (pl, 1, win_long)):
            f = fpb(15) if win else fp(10.5)
            if p >= 24:
                ax.text(sign * (25 if win else p / 2 + 0.4), y, f"{p:.1f}%", ha="center", va="center",
                        color="white" if win else INK, fontproperties=f)
            else:
                ax.text(sign * (p + 2), y, f"{p:.1f}%", ha="left" if sign > 0 else "right", va="center",
                        color=INK if win else INK2, fontproperties=f)
        note = f"{d['nl']+d['ns']:,} 人" if mode == "n" else f"多 {money(d['vl'])}\n空 {money(d['vs'])}"
        ax.text(108, y, note, ha="left", va="center", color=INK2, fontproperties=fp(10), linespacing=1.3)
    ax.axvline(0, color=INK2, lw=0.8)
    for x in (-50, 50):
        ax.axvline(x, color=INK, lw=1.1, ls=(0, (4, 3)), zorder=2)
        ax.text(x, len(GROUPS) - 0.42, "過半線", ha="center", va="bottom", fontproperties=fp(9), color=INK2)
    ax.set_xlim(-100, 100); ax.set_ylim(-0.6, len(GROUPS) - 0.4)
    ax.set_xticks([-100, -75, -50, -25, 0, 25, 50, 75, 100])
    ax.set_xticklabels(["100%", "75%", "50%", "25%", "0", "25%", "50%", "75%", "100%"], fontproperties=fp(9), color=INK2)
    ax.set_yticks([]); ax.grid(axis="x", color=GRID, lw=0.8); ax.set_axisbelow(True)
    for s in ax.spines.values(): s.set_visible(False)
    ax.tick_params(length=0)
    ax.set_title(title, fontproperties=fpb(13), color=INK, loc="left", pad=8, x=-0.33)


def draw_detail(recs, coin, title, stamp, fname):
    res = agg_groups(recs, coin)
    fig, axes = plt.subplots(2, 1, figsize=(9, 11.2), facecolor=SURF)
    fig.subplots_adjust(left=0.27, right=0.80, top=0.835, bottom=0.07, hspace=0.32)
    fig.text(0.04, 0.955, title, fontproperties=fpb(19), color=INK)
    fig.text(0.04, 0.925, "交易者依「歷史總盈虧」分成 6 群，看每一群現在偏多還是偏空", fontproperties=fp(11.5), color=INK2)
    fig.patches.append(plt.Rectangle((0.04, 0.892), 0.018, 0.012, transform=fig.transFigure, color=SHORT))
    fig.text(0.064, 0.893, "偏空（左）", fontproperties=fp(11), color=INK)
    fig.patches.append(plt.Rectangle((0.19, 0.892), 0.018, 0.012, transform=fig.transFigure, color=LONG))
    fig.text(0.214, 0.893, "偏多（右）", fontproperties=fp(11), color=INK)
    fig.text(0.36, 0.893, "深色大字＝過半的一方，淺色＝少數方", fontproperties=fp(11), color=INK2)
    _panel(axes[0], res, "n", "① 按人數（一人一票）")
    _panel(axes[1], res, "v", "② 按倉位金額（錢多的份量大）")
    fig.text(0.04, 0.022, f"資料：Hyperliquid 公開 API（排行榜帳戶，僅主站永續合約）　快照時間：{stamp}（台北）",
             fontproperties=fp(8.5), color=INK2)
    fig.savefig(fname, dpi=150, facecolor=SURF); plt.close(fig)


# ---------------------------------------------------------------- 長線位置（成本線）
def zone_of(price, lth, sth):
    if price < lth: return "bear"
    if price < sth: return "mid"
    return "strong"


def cost_info(P, L, S, now):
    days = sorted(set(P) & set(L) & set(S))
    lastL, lastS = L[days[-1]], S[days[-1]]
    return dict(price=now, lth=lastL, sth=lastS, lth_date=days[-1], zone=zone_of(now, lastL, lastS),
                gap=100 * (now / lastL - 1), drop=100 * (1 - lastL / now), up=100 * (lastS / now - 1))


def draw_cost(P, L, S, now, stamp, fname, title="06 細節圖｜長線位置：價格離長期持有者成本多遠", marks=None, mark_now=False, blue_since=None):
    c = cost_info(P, L, S, now)
    today = dt.date.fromisoformat(stamp[:10])
    days = sorted(set(P) & set(L) & set(S)); x = [dt.date.fromisoformat(d) for d in days]
    l = [L[d] for d in days]; s = [S[d] for d in days]
    pd_ = [d for d in sorted(P) if d >= days[0]]
    px = [dt.date.fromisoformat(d) for d in pd_] + [today]; pp = [P[d] for d in pd_] + [now]
    lastL, lastS, zn, gap, drop, up = c["lth"], c["sth"], c["zone"], c["gap"], c["drop"], c["up"]
    ZCOL = {"strong": INK, "mid": AMB, "bear": SHORT}

    fig = plt.figure(figsize=(9, 12.4), facecolor=SURF)
    fig.text(0.04, 0.965, title, fontproperties=fpb(18), color=INK)
    fig.text(0.04, 0.943, "長期持有者＝持幣超過約 155 天的人；成本＝他們的平均買進價（全鏈上資料，不分交易所）", fontproperties=fp(10.3), color=INK2)
    fig.patches.append(FancyBboxPatch((0.04, 0.862), 0.92, 0.066, boxstyle="round,pad=0,rounding_size=0.008", transform=fig.transFigure, fc=BOX, ec="none"))
    if gap >= 0:
        fig.text(0.058, 0.906, f"價格比長期持有者成本高 {gap:.0f}%", fontproperties=fpb(19), color=INK, va="center")
        sub = f"目前在「{ZNAME[zn]}」　再跌 {drop:.0f}% 會跌破成本線"
        if zn == "mid": sub += f"　再漲 {up:.0f}% 回到強勢區"
    else:
        fig.text(0.058, 0.906, f"價格比長期持有者成本低 {abs(gap):.0f}%（已跌破）", fontproperties=fpb(19), color=INK, va="center")
        sub = f"目前在「{ZNAME[zn]}」　歷史上屬於熊市底部區域"
    fig.text(0.058, 0.877, sub, fontproperties=fp(12), color=INK, va="center")

    # 位置尺
    ar = fig.add_axes([0.06, 0.775, 0.88, 0.06]); ar.axis("off"); ar.set_xlim(0, 1); ar.set_ylim(0, 1)
    a, b = min(lastL, lastS), max(lastL, lastS)
    lo, hi = min(a * 0.72, now * 0.9), max(b * 1.28, now * 1.1)
    t = lambda v: (math.log(v) - math.log(lo)) / (math.log(hi) - math.log(lo))
    for u, w, col, name in ((lo, lastL, ZR, "熊底區"), (lastL, max(lastS, lastL), ZA, "中間區"), (max(lastS, lastL), hi, ZB, "強勢區")):
        if t(w) - t(u) > 0.01:
            ar.add_patch(plt.Rectangle((t(u) + 0.002, 0.38), t(w) - t(u) - 0.004, 0.30, fc=col, ec="none"))
            if t(w) - t(u) > 0.09: ar.text((t(u) + t(w)) / 2, 0.53, name, ha="center", va="center", fontproperties=fpb(11), color=INK)
    for v, name in ((lastL, "長期成本"), (lastS, "短期成本")):
        ar.plot([t(v), t(v)], [0.30, 0.76], color=INK, lw=1.2)
        ar.text(t(v), 0.10, f"{name} \\${v/1000:.1f}K", ha="center", va="center", fontproperties=fp(10), color=INK2)
    tn = min(max(t(now), 0.02), 0.98)
    ar.plot([tn], [0.80], marker="v", ms=13, color=INK, clip_on=False)
    ar.text(tn, 1.08, f"現在 \\${now/1000:.1f}K", ha="center", va="center", fontproperties=fpb(11.5), color=INK)

    # 主圖
    ax = fig.add_axes([0.10, 0.215, 0.74, 0.515]); ax.set_facecolor(SURF)
    for sp in ax.spines.values(): sp.set_visible(False)
    ax.set_yscale("log"); ax.grid(color=GRID, lw=0.8); ax.set_axisbelow(True); ax.tick_params(length=0)
    allv = pp + l + s
    YLO, YHI = min(allv) * 0.90, max(allv) * 1.12
    la, sa = np.array(l), np.array(s); hi_ = np.maximum(la, sa)
    ax.fill_between(x, YLO, la, color=ZR, linewidth=0)
    ax.fill_between(x, la, hi_, color=ZA, linewidth=0)
    ax.fill_between(x, hi_, YHI, color=ZB, linewidth=0)
    xe = [x[-1], today + dt.timedelta(days=4)]
    ax.fill_between(xe, YLO, lastL, color=ZR, linewidth=0)
    ax.fill_between(xe, lastL, max(lastS, lastL), color=ZA, linewidth=0)
    ax.fill_between(xe, max(lastS, lastL), YHI, color=ZB, linewidth=0)
    ax.plot(x, s, color=INK2, lw=1.1, ls=(0, (4, 2))); ax.plot([x[-1], today], [lastS, lastS], color=INK2, lw=1, ls=":")
    ax.plot(x, l, color=LONG, lw=2.6); ax.plot([x[-1], today], [lastL, lastL], color=LONG, lw=1.4, ls=":")
    pts = np.array([mdates.date2num(px), pp]).T; segs = np.stack([pts[:-1], pts[1:]], axis=1); cols = []
    for i in range(len(px) - 1):
        d = px[i + 1].isoformat()
        if not (d in L and d in S): d = days[-1]
        cols.append(ZCOL[zone_of(pp[i + 1], L[d], S[d])])
    ax.add_collection(LineCollection(segs, colors=cols, linewidths=1.8, capstyle="round"))
    ax.set_xlim(x[0], today + dt.timedelta(days=4)); ax.set_ylim(YLO, YHI)
    ticks = [v for v in (5000, 10000, 15000, 20000, 30000, 50000, 70000, 100000, 130000, 200000, 300000, 500000) if YLO <= v <= YHI]
    ax.set_yticks(ticks); ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"${v/1000:.0f}K")); ax.minorticks_off()
    ax.xaxis.set_major_locator(mdates.YearLocator()); ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    for tk in ax.get_xticklabels() + ax.get_yticklabels(): tk.set_fontproperties(fp(10)); tk.set_color(INK2)
    ax.scatter([today], [now], s=60, color=ZCOL[zn], zorder=6, edgecolor=SURF, linewidth=2)
    kw = dict(textcoords="offset points", va="center", annotation_clip=False)
    # 右側標籤：避免重疊，依數值排序後拉開距離
    labs = sorted([(now, f"現在（即時）\n\\${now/1000:.1f}K", fpb(12), INK), (lastS, f"短期成本（{c['lth_date'][5:].replace('-','/')}）\n\\${lastS/1000:.1f}K", fp(10), INK2),
                   (lastL, f"長期成本（{c['lth_date'][5:].replace('-','/')}）\n\\${lastL/1000:.1f}K", fpb(10.5), INK)], key=lambda z: z[0])
    ypix = [ax.transData.transform((0, v))[1] for v, *_ in labs]
    adj = ypix[:]
    for i in range(1, 3):
        if adj[i] - adj[i - 1] < 62: adj[i] = adj[i - 1] + 62
    for (v, txt, f, col), y0, y1 in zip(labs, ypix, adj):
        ax.annotate(txt, (today, v), xytext=(9, (y1 - y0) * 72 / fig.dpi), fontproperties=f, color=col, **kw)
    if abs(gap) >= 4:
        xm = today - dt.timedelta(days=45)
        ax.annotate("", (xm, lastL), (xm, now), arrowprops=dict(arrowstyle="<->", color=INK, lw=1.3))
        ax.text(xm - dt.timedelta(days=12), math.sqrt(now * lastL), f"距離\n{abs(drop) if gap >= 0 else abs(gap):.0f}%", ha="right", va="center", fontproperties=fpb(11), color=INK)
    ax.text(0.24, 0.93, "強勢區：價格高於短期成本，近期買進的人在賺錢", transform=ax.transAxes, fontproperties=fp(10), color=INK2, va="center", ha="center")
    ax.text(0.60, 0.05, "熊底區：價格低於長期成本，連長期持有者都在賠錢", transform=ax.transAxes, fontproperties=fp(10), color=INK2, va="center", ha="center")
    below = [d for d in days if d in P and P[d] < L[d] and d < days[-200]] if len(days) > 400 else []
    if below:
        mn = min(100 * (P[d] / L[d] - 1) for d in below)
        i0 = days.index(below[len(below) // 4])
        ax.annotate(f"上次跌破（{below[0][:4]} 熊市）\n最深低於成本 {abs(mn):.0f}%\n{below[-1][:7]} 才站回", (x[i0], P[days[i0]]), xytext=(70, 62),
                    textcoords="offset points", fontproperties=fp(10), color=INK, va="center", arrowprops=dict(arrowstyle="-", color=INK2, lw=0.8))
    for d in (marks or []):
        if d in P:
            ax.scatter([dt.date.fromisoformat(d)], [P[d]], s=75, color=DOT, zorder=7, edgecolor=SURF, linewidth=2)
    if mark_now:
        ax.scatter([today], [now], s=420, color=DOT, alpha=0.18, zorder=7, linewidth=0)
        ax.scatter([today], [now], s=110, color=DOT, zorder=8, edgecolor=INK, linewidth=1.6)
        if blue_since:
            bd = dt.date.fromisoformat(blue_since)
            fig.text(0.942, 0.906, f"● 藍點成立中（{bd.month}/{bd.day} 起）", ha="right", va="center",
                     fontproperties=fpb(13), color="white", bbox=dict(boxstyle="round,pad=0.45", fc=DOT, ec="none"))
    ax.set_title("價格走勢與兩條成本線（價格線顏色＝當時所在區域）", fontproperties=fpb(12.5), color=INK, loc="left", pad=10)

    fig.patches.append(FancyBboxPatch((0.04, 0.058), 0.92, 0.118, boxstyle="round,pad=0,rounding_size=0.008", transform=fig.transFigure, fc=BOX, ec="none"))
    fig.text(0.058, 0.158, "怎麼看這張圖", fontproperties=fpb(12), color=INK, va="center")
    rows = [(INK, "黑色價格線", "在強勢區：市場熱，近期買進的人賺錢"), (AMB, "橘色價格線", "在中間區：近期買進的人賠錢，但長期持有者還在賺"),
            (SHORT, "紅色價格線", "在熊底區：跌破長期成本，過去出現在熊市底部，但可能再磨好幾個月")]
    if marks:
        rows = rows + [(DOT, "藍點", "鯨魚 30 天減少＋價格低於短期成本：過去多出現在短線相對低點附近")]
    for i, (col, a_, b_) in enumerate(rows):
        y = (0.136 - i * 0.022) if marks else (0.133 - i * 0.025)
        if a_ == "藍點": fig.lines.append(plt.Line2D([0.073], [y], marker="o", ms=8, color=col, transform=fig.transFigure))
        else: fig.patches.append(plt.Rectangle((0.058, y - 0.003), 0.03, 0.006, transform=fig.transFigure, color=col))
        fig.text(0.098, y, a_, fontproperties=fpb(10.5), color=INK, va="center"); fig.text(0.225, y, b_, fontproperties=fp(10.5), color=INK, va="center")
    fig.text(0.04, 0.026, f"資料：BGeometrics 免費 API（近 4 年；成本線延遲約 7 天，目前到 {c['lth_date']}，之後以虛線延伸）；價格取自 {stamp}（台北）。\n屬長線背景參考，不是短線買賣訊號。",
             fontproperties=fp(8.8), color=INK2, linespacing=1.5)
    fig.savefig(fname, dpi=150, facecolor=SURF); plt.close(fig)
    return c
