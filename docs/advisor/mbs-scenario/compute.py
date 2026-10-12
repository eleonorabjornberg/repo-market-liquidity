"""Generate the MBS scenario notes (Stage 1 facts, Stage 2 sizing draft) from tracked data.

Standard library only. Run from the repository root:

    python3 docs/advisor/mbs-scenario/compute.py          # rewrite 01-facts.md, 02-sizing.md and scenarios.csv
    python3 docs/advisor/mbs-scenario/compute.py --check  # fail if either file is stale

Inputs (all cut at 2025-12-31; nothing from 2026 is read, per the lockbox):
- tests/fixtures/snapshots/h41/h41_mbs_first_print.csv   Fed MBS holdings, H.4.1 first prints (this repo)
- tests/fixtures/snapshots/fomc_notes/runoff_caps.csv     FOMC runoff caps (this repo)
- docs/advisor/mbs-scenario/data/MORTGAGE30US.csv         Freddie Mac 30-year rate via FRED (snapshot)
- docs/advisor/mbs-scenario/data/WRESBAL.csv              reserve balances via FRED (snapshot)
- docs/advisor/mbs-scenario/data/RRPONTSYD.csv            ON RRP via FRED (snapshot)
- docs/advisor/mbs-scenario/data/TLAACBW027SBOG.csv       H.8 bank assets via FRED (snapshot)

Every figure in the two generated notes comes from these files. Prose that is not a figure is written here.
"""

import csv
import hashlib
import json
import sys
from collections import OrderedDict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
LAST_DAY = "2025-12-31"

H41 = ROOT / "tests/fixtures/snapshots/h41/h41_mbs_first_print.csv"
CAPS = ROOT / "tests/fixtures/snapshots/fomc_notes/runoff_caps.csv"
DATA = HERE / "data"


def check_manifest(name):
    path = DATA / name
    manifest = json.loads((DATA / (name + ".manifest.json")).read_text())
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != manifest["sha256"]:
        raise ValueError(f"{name}: sha256 {digest} does not match its manifest")
    return path


def fred(name):
    out = []
    with open(check_manifest(name)) as f:
        for row in csv.DictReader(f):
            key = [k for k in row if k != "observation_date"][0]
            if row[key] not in ("", ".") and row["observation_date"] <= LAST_DAY:
                out.append((row["observation_date"], float(row[key])))
    return out


def monthly_holdings():
    """Last H.4.1 week-average first print of each month, $bn, to 2025-12."""
    by_month = OrderedDict()
    with open(H41) as f:
        for row in csv.DictReader(f):
            if row["week_ended"] <= LAST_DAY:
                by_month[row["week_ended"][:7]] = float(row["week_average_musd"]) / 1000
    return by_month


def wednesday_levels():
    out = []
    with open(H41) as f:
        for row in csv.DictReader(f):
            if row["week_ended"] <= LAST_DAY:
                out.append((row["week_ended"], float(row["wednesday_level_musd"]) / 1000))
    return out


def caps_by_month(months):
    steps = []
    with open(CAPS) as f:
        for row in csv.DictReader(f):
            steps.append((row["effective_date"][:7], float(row["mbs_cap_bn"])))
    steps.sort()
    out = {}
    for m in months:
        cap = None
        for eff, value in steps:
            if m >= eff:
                cap = value
        out[m] = cap
    return out


def monthly_mean(series):
    acc = OrderedDict()
    for d, v in series:
        acc.setdefault(d[:7], []).append(v)
    return OrderedDict((m, sum(v) / len(v)) for m, v in acc.items())


def bn(x, dp=1):
    if x < 0:
        return f"−\\${-x:,.{dp}f}bn"
    return f"\\${x:,.{dp}f}bn"


def tn(x):
    return f"\\${x / 1000:,.2f}tn"


# Regimes, by month. Dates come from the FOMC documents in TIMELINE.
REGIMES = [
    ("2017-10", "2019-07", "QT1: passive runoff under a cap"),
    ("2019-08", "2020-02", "Paydowns into Treasuries (up to \\$20bn a month)"),
    ("2020-03", "2022-03", "QE: net purchases"),
    ("2022-04", "2022-05", "All paydowns reinvested in MBS"),
    ("2022-06", "2025-11", "QT2: passive runoff under a cap"),
    ("2025-12", "2025-12", "All paydowns into Treasury bills"),
]

FED = "https://www.federalreserve.gov/newsevents/pressreleases/"
TIMELINE = [
    ("14 Jun 2017", "monetary20170614c.htm",
     "First MBS runoff cap: \\$4bn a month, rising by \\$4bn every three months to \\$20bn.",
     "Runoff, not sales: the pace is set by homeowners' paydowns, up to the cap."),
    ("20 Mar 2019", "monetary20190320c.htm",
     "From Oct 2019, MBS paydowns up to \\$20bn a month go into Treasuries; the aim is to hold \"primarily Treasury securities in the longer run\".",
     "The Fed's stated preference for an all-Treasury balance sheet, the origin of the MBS problem."),
    ("31 Jul 2019", "monetary20190731a.htm",
     "Runoff ends in August, two months early.",
     "Reserve drain stops; MBS keeps shrinking as paydowns move into Treasuries (reserve-neutral)."),
    ("15 Mar 2020", "monetary20200315a.htm",
     "Buy \"at least \\$200 billion\" of agency MBS; reinvest all paydowns in MBS.",
     "QE begins: MBS purchases add reserves."),
    ("23 Mar 2020", "monetary20200323a.htm",
     "Buy MBS \"in the amounts needed\".",
     "Open-ended purchases; the holdings build that QT2 later works against."),
    ("16 Dec 2020", "monetary20201216a.htm",
     "\"At least \\$40 billion per month\" of agency MBS.",
     "The steady QE pace through 2021."),
    ("3 Nov 2021", "monetary20211103a.htm",
     "Taper: MBS purchases cut by \\$5bn a month.",
     "Reserve injection starts to slow."),
    ("15 Dec 2021", "monetary20211215a.htm",
     "Taper doubled: MBS purchases cut by \\$10bn a month.",
     "Faster end to purchases."),
    ("26 Jan 2022", "monetary20220126a.htm",
     "Net purchases end \"in early March\".",
     "Holdings peak shortly after."),
    ("4 May 2022", "monetary20220504b.htm",
     "QT2: MBS cap \\$17.5bn a month from June, \\$35bn from September.",
     "Runoff resumes; the cap is the most the Fed will let mature without reinvesting."),
    ("1 May 2024", "monetary20240501a1.htm",
     "MBS cap stays \\$35bn; paydowns above it go into Treasuries (from June).",
     "Irrelevant in practice: paydowns never reached \\$35bn (see below)."),
    ("19 Mar 2025", "monetary20250319a1.htm",
     "MBS cap stays \\$35bn (Treasury cap cut to \\$5bn from April).",
     "The MBS drain continues while the Treasury drain nearly stops."),
    ("29 Oct 2025", "monetary20251029a1.htm",
     "Runoff ends 1 Dec; \"reinvest all principal payments ... of agency securities into Treasury bills\".",
     "From December, MBS paydowns no longer drain reserves: a shift from MBS to bills."),
    ("10 Dec 2025", "monetary20251210a1.htm",
     "Reinvestment into bills repeated; reserve-management bill purchases begin.",
     "The Fed now adds reserves on purpose; any MBS scenario is measured against that."),
]


def regime_of(m):
    for start, end, label in REGIMES:
        if start <= m <= end:
            return label
    return None


def build():
    holdings = monthly_holdings()
    months = list(holdings)
    change = OrderedDict((months[i], holdings[months[i]] - holdings[months[i - 1]]) for i in range(1, len(months)))
    caps = caps_by_month(months)
    mort_w = fred("MORTGAGE30US.csv")
    mort_m = monthly_mean(mort_w)
    reserves = fred("WRESBAL.csv")
    rrp = fred("RRPONTSYD.csv")
    levels = wednesday_levels()

    def window(a, b):
        return [m for m in change if a <= m <= b]

    def avg(xs):
        return sum(xs) / len(xs)

    # Holdings history
    peak = max(levels, key=lambda x: x[1])
    year_end = OrderedDict()
    for d, v in levels:
        year_end[d[:4]] = (d, v)

    # Rules vs reality by regime
    regime_rows = []
    for start, end, label in REGIMES:
        ms = window(start, end)
        if not ms:
            continue
        red = [-change[m] for m in ms]
        cs = [caps[m] for m in ms if caps[m]]
        at_cap = sum(1 for m in ms if caps[m] and -change[m] >= caps[m] - 0.5)
        regime_rows.append((label, start, end, avg(red), max(red), avg(cs) if cs else None, at_cap, len(ms),
                            avg([mort_m[m] for m in ms])))

    qt2 = window("2022-09", "2025-11")
    qt2_avg = avg([-change[m] for m in qt2])
    qt2_max_m = max(qt2, key=lambda m: -change[m])
    qt2_at_cap = sum(1 for m in qt2 if -change[m] >= 35 - 0.5)
    qt2_rate = avg([-change[m] / holdings[months[months.index(m) - 1]] for m in qt2])
    qt2_mort = [v for d, v in mort_w if "2022-06-01" <= d <= "2025-11-30"]
    qt2_mort_dates = [(d, v) for d, v in mort_w if "2022-06-01" <= d <= "2025-11-30"]
    mort_max = max(qt2_mort_dates, key=lambda x: x[1])
    mort_min = min(qt2_mort_dates, key=lambda x: x[1])
    weeks_7 = sum(1 for v in qt2_mort if v >= 7)

    p19 = window("2019-08", "2020-02")
    p19_rate = avg([-change[m] / holdings[months[months.index(m) - 1]] for m in p19])
    p19_mort = avg([mort_m[m] for m in p19])
    p19_avg = avg([-change[m] for m in p19])

    end_holdings = holdings["2025-12"]
    res = dict(reserves)
    start_res = res["2025-12-31"] / 1000
    pressure_res = res["2025-10-29"] / 1000
    gap = start_res - pressure_res
    rrp_dec = sorted(v for d, v in rrp if d.startswith("2025-12") and d != "2025-12-31")
    rrp_dec_med = rrp_dec[len(rrp_dec) // 2]
    assets = dict(fred("TLAACBW027SBOG.csv"))
    start_assets = assets["2025-12-31"]
    pressure_assets = assets["2025-10-29"]

    return dict(holdings=holdings, change=change, caps=caps, mort_m=mort_m, peak=peak, year_end=year_end,
                regime_rows=regime_rows, qt2_avg=qt2_avg, qt2_max_m=qt2_max_m, qt2_max=-change[qt2_max_m],
                qt2_at_cap=qt2_at_cap, qt2_n=len(qt2), qt2_rate=qt2_rate, qt2_mort_avg=avg(qt2_mort),
                mort_max=mort_max, mort_min=mort_min, weeks_7=weeks_7, weeks_n=len(qt2_mort), p19_rate=p19_rate,
                p19_mort=p19_mort, p19_avg=p19_avg, end_holdings=end_holdings, start_res=start_res,
                pressure_res=pressure_res, gap=gap, rrp_dec_med=rrp_dec_med, start_assets=start_assets,
                pressure_assets=pressure_assets)


def facts(f):
    lines = []
    w = lines.append
    w("# MBS scenario, Stage 1: facts note")
    w("")
    w("*Generated by `compute.py` from tracked data, cut at 2025-12-31. Do not edit by hand. Advisor note (Nicholas Beroud);")
    w("descriptive, not a scored result.*")
    w("")
    w("\"MBS\" below means the Fed's agency securities in total: the caps and the reinvestment rules apply to agency debt and")
    w("agency MBS together, and agency debt is about \\$2.3bn, too small to change any figure here.")
    w("")
    w("## 1. Policy timeline")
    w("")
    w("| Date | What the Fed decided (MBS) | Why it matters for reserves | Source |")
    w("|---|---|---|---|")
    for date, page, what, why in TIMELINE:
        w(f"| {date} | {what} | {why} | [Fed]({FED}{page}) |")
    w("")
    w("All of these are linked from the Fed's [Policy Normalization page](https://www.federalreserve.gov/monetarypolicy/policy-normalization.htm).")
    w("Caps and effective dates match this repository's `tests/fixtures/snapshots/fomc_notes/runoff_caps.csv`.")
    w("")
    w("## 2. Holdings")
    w("")
    w("Fed MBS holdings, H.4.1 first prints (Wednesday level, last week of each year):")
    w("")
    w("| Year end | Holdings |")
    w("|---|---|")
    for y, (d, v) in f["year_end"].items():
        w(f"| {d} | {tn(v)} |")
    w("")
    w(f"Peak: **{tn(f['peak'][1])}** in the week ended {f['peak'][0]}, after QE.")
    w("")
    w("## 3. Rules vs reality")
    w("")
    w("Monthly change in holdings (from H.4.1 week-average first prints), against the cap in force and the 30-year")
    w("mortgage rate (Freddie Mac, via FRED):")
    w("")
    w("| Regime | Months | Average monthly reduction | Largest month | Average cap | Months at the cap | Average mortgage rate |")
    w("|---|---|---|---|---|---|---|")
    for label, start, end, a, mx, cap, at_cap, n, mort in f["regime_rows"]:
        capt = bn(cap) if cap else "none"
        w(f"| {label} | {start} to {end} ({n}) | {bn(a)} | {bn(mx)} | {capt} | {at_cap} of {n} | {mort:.2f}% |")
    w("")
    w("A negative reduction is growth (QE purchases). Single months are noisy: MBS purchases and reinvestments settle")
    w("on fixed monthly dates, so one month can swing well above or below the cap and the next swing back. Read the")
    w("averages; the \"months at the cap\" count is indicative only.")
    w("")
    w("## 4. What the facts show")
    w("")
    w(f"1. **The \\$35bn cap never bound.** From Sep 2022 to Nov 2025 the reduction averaged **{bn(f['qt2_avg'])} a month**,")
    w(f"   at most {bn(f['qt2_max'])} ({f['qt2_max_m']}), and reached the cap in {f['qt2_at_cap']} of {f['qt2_n']} months. The cap")
    w("   was a ceiling the market never tested; the realized pace is the measure that matters.")
    w(f"2. **Mortgage rates set the pace.** Over QT2 the 30-year rate averaged {f['qt2_mort_avg']:.2f}% (range")
    w(f"   {f['mort_min'][1]:.2f}% on {f['mort_min'][0]} to {f['mort_max'][1]:.2f}% on {f['mort_max'][0]}; at or above 7% in")
    w(f"   {f['weeks_7']} of {f['weeks_n']} weeks), and holdings fell about {f['qt2_rate'] * 100:.2f}% a month. From Aug 2019 to")
    w(f"   Feb 2020, with the rate around {f['p19_mort']:.2f}%, they fell about {f['p19_rate'] * 100:.2f}% a month, and that was")
    w("   with paydowns above \\$20bn reinvested, so it understates the true prepayment pace. Lower rates, faster runoff.")
    w("3. **A cap of zero does not mean MBS stops shrinking.** After Aug 2019 and from Dec 2025, paydowns kept running off")
    w("   MBS but were reinvested into Treasuries, then bills. Holdings fall; reserves do not. The reserve effect depends")
    w("   on where paydowns are reinvested, not on the MBS line alone.")
    w("4. **The Fed has wanted out of MBS since 2019** (\"primarily Treasury securities in the longer run\"), yet in")
    w("   practice it has only ever let MBS run off. It has never sold outright, which is what makes active sales the")
    w("   tail scenario.")
    w("")
    w("## Sources")
    w("")
    w("- Holdings: `tests/fixtures/snapshots/h41/h41_mbs_first_print.csv` (H.4.1 first prints).")
    w("- Caps: `tests/fixtures/snapshots/fomc_notes/runoff_caps.csv`.")
    w("- Mortgage rate: `docs/advisor/mbs-scenario/data/MORTGAGE30US.csv` (FRED, Freddie Mac PMMS), with its manifest.")
    w("- FOMC statements and implementation notes: linked in the timeline.")
    return "\n".join(lines) + "\n"


RMP_ANNOUNCED = 40.0
RMP_SOURCE = "https://www.newyorkfed.org/markets/opolicy/operating_policy_251210a"
SATIATION_BAND = (12.0, 13.0)  # NY Fed SR 1019: reserves as % of bank assets
SR1019 = "https://www.newyorkfed.org/medialibrary/media/research/staff_reports/sr1019.pdf"
HORIZON = 24  # months, Jan 2026 to Dec 2027
REPO_SHARE = 0.5  # illustrative share of outright sales financed in repo (not observed)


def scenarios(f):
    s1 = f["qt2_avg"]
    s3 = f["p19_rate"] * f["end_holdings"]
    return [
        ("S0", "Baseline: paydowns keep going into bills (as since Dec 2025)", 0.0, 0.0),
        ("S1", "Reinvestment stops; passive runoff resumes at the QT2 realized pace", s1, 0.0),
        ("S2", "Active sales fill the gap to the \\$35bn cap", 35.0, 35.0 - s1),
        ("S2-high", "Sales of \\$35bn a month on top of passive runoff (sensitivity)", 35.0 + s1, 35.0),
        ("S3", "A rate drop revives prepayments under runoff (lower bound from 2019–20)", s3, 0.0),
    ]


def months_to(room, net_drain):
    return "never" if net_drain <= 0 else f"{room / net_drain:.1f}"


def sizing(f):
    s1 = f["qt2_avg"]
    s1_rate = f["qt2_rate"] * f["end_holdings"]
    r_start = 100 * f["start_res"] / f["start_assets"]
    r_press = 100 * f["pressure_res"] / f["pressure_assets"]
    # room to the Oct 2025 ratio, holding bank assets at their end-2025 level
    ratio_room = (r_start - r_press) / 100 * f["start_assets"]
    scen = scenarios(f)
    lines = []
    w = lines.append
    w("# MBS scenario, Stage 2: sizing")
    w("")
    w("*Generated by `compute.py` from tracked data, cut at 2025-12-31. Do not edit by hand. Advisor note (Nicholas Beroud);")
    w("scenarios are stated assumptions, not forecasts, and nothing here is scored. Complete for review: the two open")
    w("questions of the first draft are answered below as proposals.*")
    w("")
    w("## Starting point (all pre-2026)")
    w("")
    w(f"- Fed MBS holdings, Dec 2025: **{tn(f['end_holdings'])}**.")
    w(f"- Reserve balances, 31 Dec 2025: **{tn(f['start_res'])}**; bank assets (H.8, all commercial banks): {tn(f['start_assets'])}.")
    w(f"- Reserves as a share of bank assets: **{r_start:.2f}%** at end-2025, against **{r_press:.2f}%** in the week of the Oct 2025")
    w(f"  pressure peak (29 Oct 2025). The NY Fed's estimate puts satiation at about {SATIATION_BAND[0]:.0f}–{SATIATION_BAND[1]:.0f}% of bank")
    w(f"  assets ([SR 1019]({SR1019})), so end-2025 sits just below the bottom of that band and Oct 2025 a little further below.")
    w(f"- ON RRP, Dec 2025 median (excluding year-end): {bn(f['rrp_dec_med'])}. The buffer is effectively empty, so a")
    w("  drain comes out of reserves directly.")
    w(f"- The Fed's reserve-management bill purchases (RMPs): about **{bn(RMP_ANNOUNCED, 0)} a month** in the first schedule,")
    w(f"  from 12 Dec 2025, described as elevated \"for a few months\" and then \"significantly reduced\" ([NY Fed]({RMP_SOURCE})).")
    w("  Only that December 2025 announcement is used; nothing later.")
    w("")
    w("## Two yardsticks")
    w("")
    w(f"- **Level:** reserves falling back to their Oct 2025 pressure level, {tn(f['pressure_res'])}. Room: **{bn(f['gap'], 0)}**.")
    w(f"- **Ratio:** reserves-to-assets falling back to its Oct 2025 level, {r_press:.2f}%, with bank assets held at")
    w(f"  their end-2025 level. Room: **{bn(ratio_room, 0)}**. This is the measure the scarcity state and SR 1019 use, and")
    w("  it allows for the growth of bank balance sheets; the level does not.")
    w("")
    w("## Scenarios")
    w("")
    w("Months until the yardstick is reached, holding everything else equal (TGA, currency, bank assets):")
    w("")
    w("| | Scenario | Drain per month | Of which sales | Months, level (RMPs stop) | Months, ratio (RMPs stop) | Net of RMPs at \\$40bn | Months, ratio (RMPs continue) |")
    w("|---|---|---|---|---|---|---|---|")
    for key, label, drain, sales in scen:
        net = drain - RMP_ANNOUNCED
        net_txt = f"adds {bn(-net)}" if net < 0 else f"drains {bn(net)}"
        w(f"| **{key}** | {label} | {bn(drain)} | {bn(sales)} | {months_to(f['gap'], drain)} | "
          f"{months_to(ratio_room, drain)} | {net_txt} | {months_to(ratio_room, net)} |")
    w("")
    w("**What the table says.**")
    w("1. **With RMPs stopped, every runoff or sales scenario reaches the Oct 2025 pressure level within months.** The")
    w(f"   fastest, S2-high, takes about {months_to(ratio_room, scen[3][2])} months on the ratio yardstick; S1, plain runoff, about")
    w(f"   {months_to(ratio_room, scen[1][2])}.")
    w("2. **At the announced initial RMP pace, only S2-high still drains reserves.** The Fed's bill purchases more than")
    w("   offset plain runoff, sales to the cap and revived prepayments. The MBS risk to repo is therefore a question of")
    w("   what the Fed does with RMPs at the same time as with MBS: sales into a period of reduced RMPs are the case that")
    w("   bites.")
    w("")
    w("Notes on the inputs:")
    w(f"- **S1** uses the QT2 average reduction, {bn(s1)} a month, as agreed on #1. Scaled to Dec 2025 holdings at the QT2")
    w(f"  runoff rate ({f['qt2_rate'] * 100:.2f}% a month) it would be {bn(s1_rate)}.")
    w(f"- **S2** is the pace agreed on #1: sales of about {bn(35 - s1)} a month, so the total runs at the cap.")
    w(f"- **S3** applies the Aug 2019 – Feb 2020 runoff rate ({f['p19_rate'] * 100:.2f}% a month, mortgage rate about")
    w(f"  {f['p19_mort']:.2f}%) to Dec 2025 holdings, so it describes mortgage rates falling back to about that level. It is a")
    w("  lower bound: paydowns above \\$20bn were reinvested then. If a \\$35bn cap were back in force, S3's drain would sit")
    w("  between this figure and \\$35bn.")
    w("- **The yardstick is a reserves measure, not a threshold.** The evidence pack's re-check (repo-market-model#96) found")
    w("  pressure needs a thin buffer *and* tight reserves; with ON RRP near zero the first condition already holds.")
    w("")
    w("## The double hit in S2")
    w("")
    w("Outright sales do two things at once:")
    w("1. **Reserves fall** by the amount sold.")
    w("2. **Repo demand rises.** Whoever buys the MBS finances part of them in repo: dealers holding inventory, and")
    w("   levered holders such as mortgage REITs, which fund agency MBS in repo at roughly 7–8 times equity.")
    w("")
    w("Added repo demand per month = (share of sales financed in repo) × (sales). Illustration only; the share is not")
    w("observed:")
    w("")
    w("| Share financed in repo | S2 | S2-high |")
    w("|---|---|---|")
    for share in (0.25, 0.5, 1.0):
        w(f"| {share:.0%} | {bn(share * (35 - s1))} | {bn(share * 35)} |")
    w("")
    w("Falling MBS prices would also raise margin calls on levered holders, who may sell into the same market: a")
    w("feedback the table cannot size.")
    w("")
    w("## Hand-off for Stage 3 (H7): `scenarios.csv`")
    w("")
    w(f"Every scenario as a monthly path over {HORIZON} months from the end-2025 state, under both RMP assumptions, in")
    w("`scenarios.csv` (generated with this note). Columns:")
    w("")
    w("| Column | Meaning |")
    w("|---|---|")
    w("| `scenario`, `rmp` | Scenario key; `stop` or `announced` (\\$40bn a month) |")
    w("| `month` | Calendar month of the path (a scenario month, not data) |")
    w("| `agency_change_bn` | Change in Fed agency securities from runoff and sales (negative = fall) |")
    w("| `sales_bn` | Outright sales in the month |")
    w("| `rmp_bn` | Reserve-management purchases assumed in the month |")
    w("| `reserves_change_bn` | Net change in reserves, all else equal |")
    w("| `reserves_bn`, `reserves_to_assets_pct` | Level and ratio at month end (bank assets held at end-2025) |")
    w(f"| `repo_demand_bn` | Illustrative added repo demand, at {REPO_SHARE:.0%} of sales financed in repo |")
    w("")
    w("These are known flows for the deployable-liquidity model to take as scenario inputs. They are assumptions, not")
    w("observations, and must not enter any scored run.")
    w("")
    w("## Proposed answers to the two questions in the first draft (for Eleonora to confirm)")
    w("")
    w("1. **Yardstick: use the ratio as primary, the level as a cross-check.** It matches SR 1019 and the scarcity state,")
    w("   and allows for growth in bank balance sheets.")
    w("2. **RMPs: report both.** \"RMPs stop\" is the stress case for S2; \"RMPs continue\" shows the offset. The finding")
    w("   that the Fed's bill purchases decide whether MBS runoff bites at all is itself the result for the narrative.")
    return "\n".join(lines) + "\n"


def scenario_csv(f):
    r0 = f["start_res"]
    a0 = f["start_assets"]
    rows = ["scenario,rmp,month,agency_change_bn,sales_bn,rmp_bn,reserves_change_bn,reserves_bn,"
            "reserves_to_assets_pct,repo_demand_bn"]
    for key, _label, drain, sales in scenarios(f):
        for rmp_label, rmp in (("stop", 0.0), ("announced", RMP_ANNOUNCED)):
            level = r0
            for i in range(HORIZON):
                year, month = 2026 + i // 12, i % 12 + 1
                change = rmp - drain
                level += change
                rows.append(f"{key},{rmp_label},{year}-{month:02d},{0.0 - drain + 0.0:.1f},{sales:.1f},{rmp:.1f},{change:.1f},"
                            f"{level:.1f},{100 * level / a0:.2f},{REPO_SHARE * sales:.1f}")
    return "\n".join(rows) + "\n"


def main():
    f = build()
    out = {HERE / "01-facts.md": facts(f), HERE / "02-sizing.md": sizing(f), HERE / "scenarios.csv": scenario_csv(f)}
    if "--check" in sys.argv:
        stale = [p.name for p, text in out.items() if not p.exists() or p.read_text() != text]
        if stale:
            raise SystemExit(f"stale: {', '.join(stale)}; run compute.py")
        print("ok")
        return
    for p, text in out.items():
        p.write_text(text)
        print(f"wrote {p.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
