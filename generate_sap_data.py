#!/usr/bin/env python3
"""
Generate synthetic SAP-style source data for a fictional convenience store chain.

The output mimics what an SAP ECC extract looks like when it lands in a
cloud warehouse: real SAP table and column names, leading-zero keys,
YYYYMMDD date strings, and document types that change the meaning of a row.
That gives the dbt staging layer real translation work to do.

Tables written (one CSV each, header row, comma-delimited):
    T001W        Plants (stores)
    ZSTORE_ATTR  Custom "Z" table with store attributes (format, sq ft, open date)
    T023T        Material group (category) descriptions
    MARA         Material master (products)
    MAKT         Material descriptions
    VBRK         Billing document headers (one per POS basket)
    VBRP         Billing document line items

Data quirks built in on purpose (handle them in dbt staging):
    * MATNR is 18 characters with leading zeros; VBELN is 10; POSNR is 6.
    * Dates are 'YYYYMMDD' strings, times are 'HHMMSS'. '00000000' means null.
    * FKART = 'ZPOS' is a sale, 'ZRET' is a return, 'S1' cancels another doc.
      Returns and cancellations store POSITIVE amounts; the doc type sets the
      sign. Cancelled originals carry FKSTO = 'X'; S1 docs point back to them
      through SFAKN.
    * Some stores open partway through the date range, and some products launch
      or are discontinued (MARA.LVORM = 'X') partway through.
    * Fuel is sold in gallons (GAL) with a monthly price; everything else is
      sold in eaches (EA).

Usage:
    python generate_sap_data.py                      # defaults: ~0.7M line items, ~80 MB
    python generate_sap_data.py --baskets 10         # smaller/faster
    python generate_sap_data.py --start 2024-01-01 --end 2025-12-31 --out sap_raw --seed 42

Standard library only; no installs needed.
"""

import argparse
import csv
import math
import random
from datetime import date, timedelta
from pathlib import Path

# --------------------------------------------------------------------------
# Reference data
# --------------------------------------------------------------------------

# (city, state, zip, district, has_fuel, size_factor, open_date or None)
STORES = [
    ("Media",            "PA", "19063", "D01", True,  1.20, None),
    ("Springfield",      "PA", "19064", "D01", True,  1.05, None),
    ("Broomall",         "PA", "19008", "D01", False, 0.85, None),
    ("Havertown",        "PA", "19083", "D01", False, 0.90, None),
    ("West Chester",     "PA", "19380", "D02", True,  1.15, None),
    ("Exton",            "PA", "19341", "D02", True,  1.25, None),
    ("Downingtown",      "PA", "19335", "D02", True,  0.95, "2025-03-15"),
    ("King of Prussia",  "PA", "19406", "D02", True,  1.30, None),
    ("Philadelphia",     "PA", "19103", "D03", False, 1.10, None),
    ("Philadelphia",     "PA", "19147", "D03", False, 0.95, None),
    ("Conshohocken",     "PA", "19428", "D03", True,  1.00, None),
    ("Cherry Hill",      "NJ", "08002", "D04", True,  1.20, None),
    ("Voorhees",         "NJ", "08043", "D04", True,  1.00, None),
    ("Mount Laurel",     "NJ", "08054", "D04", True,  1.10, "2024-09-01"),
    ("Glassboro",        "NJ", "08028", "D04", False, 0.80, None),
    ("Wilmington",       "DE", "19801", "D05", False, 0.90, None),
    ("Newark",           "DE", "19711", "D05", True,  1.05, None),
    ("Middletown",       "DE", "19709", "D05", True,  0.95, None),
    ("Elkton",           "MD", "21921", "D05", True,  0.85, None),
    ("Bel Air",          "MD", "21014", "D05", True,  1.00, "2025-06-01"),
]

# Category: (material group, description, tax rate, cost ratio)
CATEGORIES = {
    "FUEL01": ("Fuel",                 0.000, 0.88),
    "BEV01":  ("Hot Beverages",        0.060, 0.25),
    "BEV02":  ("Cold Dispensed Bev",   0.060, 0.22),
    "BEV03":  ("Packaged Beverages",   0.060, 0.55),
    "FOOD01": ("Sandwiches & Hoagies", 0.060, 0.45),
    "FOOD02": ("Breakfast",            0.060, 0.40),
    "FOOD03": ("Bakery",               0.060, 0.35),
    "FOOD04": ("Hot Foods",            0.060, 0.42),
    "SNK01":  ("Salty Snacks",         0.060, 0.58),
    "SNK02":  ("Candy & Gum",          0.060, 0.55),
    "GRO01":  ("Grocery & Dairy",      0.000, 0.70),
    "HBA01":  ("Health & Beauty",      0.060, 0.50),
}


def _sized(names, sizes, base, step):
    """Expand names x sizes into (description, price) pairs."""
    out = []
    for n in names:
        for i, s in enumerate(sizes):
            out.append((f"{n} {s}", round(base + step * i, 2)))
    return out


# Products per category: list of (description, list price)
CATALOG = {
    "FUEL01": [("Regular Unleaded 87", 0.0), ("Plus Unleaded 89", 0.0),
               ("Premium Unleaded 93", 0.0), ("Diesel", 0.0)],
    "BEV01": _sized(["Coffee House Blend", "Coffee Dark Roast", "Coffee Decaf",
                     "Coffee French Vanilla", "Coffee Hazelnut"],
                    ["12oz", "16oz", "20oz", "24oz"], 1.79, 0.30)
             + _sized(["Cappuccino", "Hot Chocolate", "Hot Tea"],
                      ["12oz", "16oz", "20oz"], 1.99, 0.30),
    "BEV02": _sized(["Iced Coffee", "Fountain Soda", "Lemonade", "Iced Tea Fresh Brewed"],
                    ["16oz", "24oz", "32oz"], 1.49, 0.40)
             + _sized(["Smoothie Strawberry Banana", "Smoothie Mango"],
                      ["16oz", "24oz"], 4.29, 1.00),
    "BEV03": [("Cola 20oz", 2.29), ("Diet Cola 20oz", 2.29), ("Lemon-Lime Soda 20oz", 2.29),
              ("Cola 2L", 3.29), ("Spring Water 16.9oz", 1.49), ("Spring Water 1L", 2.19),
              ("Sparkling Water Lime 17oz", 1.99), ("Sports Drink Fruit Punch 28oz", 2.79),
              ("Sports Drink Lemon-Lime 28oz", 2.79), ("Energy Drink Original 16oz", 3.49),
              ("Energy Drink Sugar Free 16oz", 3.49), ("Iced Tea Lemon 18.5oz", 2.19),
              ("Orange Juice 12oz", 2.69), ("Chocolate Milk 16oz", 2.49),
              ("Cold Brew Bottled 11oz", 3.79)],
    "FOOD01": _sized(["Italian Hoagie", "Turkey & Provolone Hoagie", "Ham & Swiss Hoagie",
                      "Chicken Cheesesteak", "Meatball Parm", "Veggie Hoagie",
                      "Tuna Salad Hoagie", "Buffalo Chicken Hoagie"],
                     ["6in", "12in"], 5.99, 2.80),
    "FOOD02": [("Sausage Egg & Cheese Sandwich", 3.99), ("Bacon Egg & Cheese Bagel", 4.29),
               ("Breakfast Burrito", 4.49), ("Egg White Veggie Wrap", 4.79),
               ("Pork Roll Egg & Cheese", 4.29), ("Oatmeal Cup", 2.99),
               ("Breakfast Bowl", 5.49)],
    "FOOD03": [("Glazed Donut", 1.29), ("Chocolate Frosted Donut", 1.39),
               ("Blueberry Muffin", 2.29), ("Plain Bagel", 1.49), ("Butter Croissant", 2.49),
               ("Chocolate Chip Cookie", 1.29), ("Soft Pretzel", 1.79), ("Cinnamon Bun", 2.79)],
    "FOOD04": [("Mac & Cheese Bowl", 5.49), ("Chicken Noodle Soup 16oz", 4.49),
               ("Tomato Soup 16oz", 4.29), ("Beef Hot Dog", 2.49), ("Chicken Tenders 5pc", 6.99),
               ("Pepperoni Pizza Slice", 3.49), ("Cheese Quesadilla", 5.99),
               ("Chicken Burrito Bowl", 8.49)],
    "SNK01": [("Potato Chips Classic 2.5oz", 2.19), ("Potato Chips BBQ 2.5oz", 2.19),
              ("Tortilla Chips Nacho 2.75oz", 2.29), ("Pretzels 3oz", 1.99),
              ("Cheese Puffs 2oz", 1.99), ("Beef Jerky 2.85oz", 7.99),
              ("Trail Mix 3oz", 3.49), ("Popcorn White Cheddar 2oz", 2.49)],
    "SNK02": [("Milk Chocolate Bar", 1.99), ("Peanut Butter Cups", 2.09),
              ("Gummy Bears 5oz", 2.49), ("Mint Gum 15pc", 1.79), ("Sour Candy 4oz", 2.29),
              ("Caramel Nougat Bar", 1.99), ("Breath Mints", 1.89)],
    "GRO01": [("Whole Milk Gallon", 3.99), ("2% Milk Gallon", 3.99), ("Eggs Large Dozen", 3.49),
              ("White Bread Loaf", 2.99), ("Butter 1lb", 4.99), ("Bananas Each", 0.39),
              ("Ice 10lb Bag", 3.29), ("Paper Towels 2pk", 4.49)],
    "HBA01": [("Pain Reliever 24ct", 6.99), ("Allergy Relief 12ct", 8.49),
              ("Lip Balm", 2.99), ("Phone Charging Cable", 12.99), ("Hand Sanitizer 2oz", 2.49),
              ("Antacid Chewables 12ct", 3.99)],
}

# How often each category shows up on a basket line (before hour/season effects)
CATEGORY_BASE_WEIGHT = {
    "FUEL01": 2.2, "BEV01": 3.0, "BEV02": 1.6, "BEV03": 2.4, "FOOD01": 1.6,
    "FOOD02": 1.2, "FOOD03": 1.0, "FOOD04": 0.9, "SNK01": 1.3, "SNK02": 1.1,
    "GRO01": 0.6, "HBA01": 0.25,
}

# Hours of the day each category peaks: list of (peak hour, width, strength)
CATEGORY_PEAKS = {
    "FUEL01": [(8, 2.0, 1.0), (17, 2.5, 1.1)],
    "BEV01":  [(7, 1.8, 2.2), (14, 2.5, 0.5)],
    "BEV02":  [(13, 3.0, 1.2), (17, 2.5, 0.8)],
    "BEV03":  [(12, 3.5, 1.0), (17, 3.0, 0.8)],
    "FOOD01": [(12, 1.5, 2.0), (18, 1.8, 1.3)],
    "FOOD02": [(7, 1.6, 2.2)],
    "FOOD03": [(7, 2.0, 1.5), (15, 2.5, 0.4)],
    "FOOD04": [(12, 1.8, 1.2), (18, 2.0, 1.4), (23, 2.0, 0.5)],
    "SNK01":  [(15, 3.0, 1.2), (21, 2.5, 0.7)],
    "SNK02":  [(15, 3.0, 1.1), (21, 2.5, 0.8)],
    "GRO01":  [(9, 3.0, 0.7), (18, 2.5, 1.0)],
    "HBA01":  [(12, 5.0, 0.8)],
}

# Basket traffic by hour (0-23), shaped like a c-store day: morning + lunch + evening peaks
HOUR_TRAFFIC = [0.6, 0.4, 0.3, 0.3, 0.5, 1.5, 3.8, 5.6, 5.4, 4.2, 3.6, 4.3,
                5.2, 4.6, 4.0, 4.3, 4.9, 5.2, 4.6, 3.6, 2.9, 2.3, 1.6, 1.0]

DOW_FACTOR = [1.00, 1.02, 1.03, 1.04, 1.10, 0.92, 0.82]  # Mon..Sun

# Average monthly retail price per gallon for Regular; other grades add a spread
FUEL_SPREAD = {"Regular Unleaded 87": 0.00, "Plus Unleaded 89": 0.40,
               "Premium Unleaded 93": 0.80, "Diesel": 0.65}
FUEL_GRADE_WEIGHT = {"Regular Unleaded 87": 0.70, "Plus Unleaded 89": 0.10,
                     "Premium Unleaded 93": 0.12, "Diesel": 0.08}

ANNUAL_GROWTH = 0.04          # same-store traffic growth per year
ANNUAL_PRICE_INCREASE = 0.03  # non-fuel list price increase each Jan 1
RETURN_RATE = 0.003           # share of baskets that later get a return doc
CANCEL_RATE = 0.002           # share of baskets that get cancelled (S1 doc)
POS_CUSTOMER = "0000900000"   # one-time POS customer (KUNAG)
SALES_ORG = "1000"


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

def d8(d):
    """date -> 'YYYYMMDD'."""
    return d.strftime("%Y%m%d")


def peak_weight(peaks, hour):
    """Sum of Gaussian bumps (wrapping around midnight) plus a small floor."""
    w = 0.08
    for center, width, strength in peaks:
        diff = min(abs(hour - center), 24 - abs(hour - center))
        w += strength * math.exp(-0.5 * (diff / width) ** 2)
    return w


def season_factor(cat, month):
    """Category seasonality; month 1-12. cos peaks in Jan, -cos peaks in Jul."""
    c = math.cos(2 * math.pi * (month - 1) / 12)
    if cat == "BEV01":
        return 1 + 0.22 * c
    if cat in ("BEV02", "BEV03"):
        return 1 - 0.25 * c
    if cat == "FOOD04":
        return 1 + 0.15 * c
    if cat == "FUEL01":
        return 1 - 0.08 * c
    if cat == "GRO01":
        return 1 + (0.25 if month in (11, 12) else 0) - (0.1 * c if month in (6, 7, 8) else 0)
    return 1.0


def traffic_season(month):
    """Overall basket traffic: a bit higher in summer, softer in Jan/Feb."""
    return 1 - 0.07 * math.cos(2 * math.pi * (month - 1) / 12)


def build_fuel_prices(rng, start, end):
    """Monthly Regular price via a bounded random walk with summer bumps."""
    prices = {}
    p = 3.35
    y, m = start.year, start.month
    while (y, m) <= (end.year, end.month):
        p += rng.gauss(0, 0.08) + (0.06 if m in (4, 5, 6) else -0.03 if m in (10, 11) else 0)
        p = min(max(p, 2.89), 4.29)
        prices[(y, m)] = round(p, 3)
        m += 1
        if m == 13:
            y, m = y + 1, 1
    return prices


def poisson_ish(rng, mean):
    """Fast approximate Poisson draw for large means."""
    return max(0, int(round(rng.gauss(mean, math.sqrt(mean)))))


# --------------------------------------------------------------------------
# Master data
# --------------------------------------------------------------------------

def build_materials(rng, start, end):
    """Return a list of material dicts plus the per-category popularity weights."""
    span = (end - start).days
    materials = []
    seq = 100000
    for cat, items in CATALOG.items():
        for desc, price in items:
            seq += 1
            launch, disc = None, None
            if cat != "FUEL01":
                r = rng.random()
                if r < 0.07:   # new item launched partway through
                    launch = start + timedelta(days=rng.randint(int(span * 0.4), int(span * 0.8)))
                elif r < 0.12:  # discontinued partway through
                    disc = start + timedelta(days=rng.randint(int(span * 0.3), int(span * 0.7)))
            materials.append({
                "matnr": str(seq).zfill(18),
                "matkl": cat,
                "desc": desc,
                "price": price,
                "uom": "GAL" if cat == "FUEL01" else "EA",
                "launch": launch,
                "disc": disc,
                # Popularity: skewed so a few items in each category dominate
                "pop": (FUEL_GRADE_WEIGHT[desc] if cat == "FUEL01"
                        else rng.paretovariate(1.6)),
                "created": launch or (start - timedelta(days=rng.randint(200, 2500))),
            })
    return materials


def write_master_data(out, rng, materials):
    with open(out / "T001W.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["MANDT", "WERKS", "NAME1", "STRAS", "ORT01", "REGIO", "PSTLZ", "LAND1", "VKORG"])
        for i, (city, st, zipc, *_rest) in enumerate(STORES):
            werks = str(1001 + i)
            street = f"{rng.randint(100, 9999)} {rng.choice(['Main St', 'Market St', 'Baltimore Ave', 'Lancaster Ave', 'Route 1', 'High St', 'Church Rd', 'Pike Rd'])}"
            w.writerow(["100", werks, f"Store {werks} {city}", street, city.upper(), st, zipc, "US", SALES_ORG])

    with open(out / "ZSTORE_ATTR.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["MANDT", "WERKS", "STORE_FORMAT", "FUEL_FLAG", "SQ_FT", "FUEL_POSITIONS",
                    "DISTRICT", "OPEN_DATE", "CLOSE_DATE"])
        for i, (city, st, zipc, district, fuel, size, opened) in enumerate(STORES):
            open_d = date.fromisoformat(opened) if opened else date(rng.randint(2002, 2019), rng.randint(1, 12), 1)
            sqft = int(round(4200 * size + rng.randint(-300, 300), -1))
            w.writerow(["100", str(1001 + i), "SUPER" if fuel else "CORE", "X" if fuel else "",
                        sqft, (8 if size < 1.1 else 12) if fuel else 0, district, d8(open_d), "00000000"])

    with open(out / "T023T.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["MANDT", "SPRAS", "MATKL", "WGBEZ"])
        for cat, (name, _tax, _cost) in CATEGORIES.items():
            w.writerow(["100", "E", cat, name])

    with open(out / "MARA.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["MANDT", "MATNR", "ERSDA", "LVORM", "MTART", "MATKL", "MEINS", "BRGEW", "GEWEI"])
        for m in materials:
            w.writerow(["100", m["matnr"], d8(m["created"]), "X" if m["disc"] else "",
                        "HAWA", m["matkl"], m["uom"],
                        "" if m["uom"] == "GAL" else f"{rng.uniform(0.05, 4.0):.3f}",
                        "" if m["uom"] == "GAL" else "LB"])

    with open(out / "MAKT.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["MANDT", "MATNR", "SPRAS", "MAKTX"])
        for m in materials:
            w.writerow(["100", m["matnr"], "E", m["desc"].upper()[:40]])


# --------------------------------------------------------------------------
# Transactions
# --------------------------------------------------------------------------

def generate_sales(out, rng, materials, start, end, baskets_per_hour_base):
    fuel_prices = build_fuel_prices(rng, start, end)
    by_cat = {}
    for m in materials:
        by_cat.setdefault(m["matkl"], []).append(m)
    cats = list(CATALOG.keys())

    # Pre-compute per-hour category weights (season applied per month later)
    hour_cat_w = [[CATEGORY_BASE_WEIGHT[c] * peak_weight(CATEGORY_PEAKS[c], h) for c in cats]
                  for h in range(24)]
    hour_total = sum(HOUR_TRAFFIC)
    hour_share = [x / hour_total for x in HOUR_TRAFFIC]

    stores = []
    for i, (city, st, zipc, district, fuel, size, opened) in enumerate(STORES):
        stores.append({
            "werks": str(1001 + i),
            "fuel": fuel,
            "size": size * rng.uniform(0.9, 1.1),
            "open": date.fromisoformat(opened) if opened else None,
        })

    vbeln_seq = 9000000000
    n_head = n_line = 0
    pending = []  # (due_date, kind, original header, original lines)

    fk = open(out / "VBRK.csv", "w", newline="")
    fp = open(out / "VBRP.csv", "w", newline="")
    wk, wp = csv.writer(fk), csv.writer(fp)
    wk.writerow(["MANDT", "VBELN", "FKART", "VKORG", "FKDAT", "ERDAT", "ERZET", "KUNAG",
                 "WAERK", "NETWR", "MWSBK", "FKSTO", "SFAKN"])
    wp.writerow(["MANDT", "VBELN", "POSNR", "MATNR", "MATKL", "WERKS", "FKIMG", "VRKME",
                 "NETWR", "WAVWR", "MWSBP"])

    def next_vbeln():
        nonlocal vbeln_seq
        vbeln_seq += 1
        return str(vbeln_seq)

    def write_doc(vbeln, fkart, day, hhmmss, lines, fksto="", sfakn=""):
        nonlocal n_head, n_line
        net = round(sum(l["net"] for l in lines), 2)
        tax = round(sum(l["tax"] for l in lines), 2)
        wk.writerow(["100", vbeln, fkart, SALES_ORG, d8(day), d8(day), hhmmss, POS_CUSTOMER,
                     "USD", f"{net:.2f}", f"{tax:.2f}", fksto, sfakn])
        for i, l in enumerate(lines, start=1):
            wp.writerow(["100", vbeln, str(i * 10).zfill(6), l["matnr"], l["matkl"], l["werks"],
                         f"{l['qty']:.3f}", l["uom"], f"{l['net']:.2f}", f"{l['cost']:.2f}",
                         f"{l['tax']:.2f}"])
            n_line += 1
        n_head += 1

    day = start
    while day <= end:
        years_in = (day - start).days / 365.25
        growth = (1 + ANNUAL_GROWTH) ** years_in
        price_mult = (1 + ANNUAL_PRICE_INCREASE) ** (day.year - start.year)
        month = day.month
        season = [season_factor(c, month) for c in cats]
        reg_price = fuel_prices[(day.year, month)]
        dow = DOW_FACTOR[day.weekday()]
        live = [m for m in materials
                if (m["launch"] is None or m["launch"] <= day) and (m["disc"] is None or m["disc"] > day)]
        live_by_cat = {}
        for m in live:
            live_by_cat.setdefault(m["matkl"], []).append(m)

        for s in stores:
            if s["open"] and day < s["open"]:
                continue
            # New stores ramp up over their first 90 days
            ramp = 1.0
            if s["open"] and (day - s["open"]).days < 90:
                ramp = 0.55 + 0.45 * (day - s["open"]).days / 90
            day_mean = baskets_per_hour_base * 24 * s["size"] * dow * traffic_season(month) * growth * ramp
            n_baskets = poisson_ish(rng, day_mean)
            hours = rng.choices(range(24), weights=hour_share, k=n_baskets)
            hours.sort()
            for h in hours:
                weights = [hour_cat_w[h][i] * season[i] for i in range(len(cats))]
                if not s["fuel"]:
                    weights[0] = 0.0
                n_items = rng.choices([1, 2, 3, 4, 5], weights=[44, 30, 15, 7, 4])[0]
                chosen = rng.choices(cats, weights=weights, k=n_items)
                # Fuel at most once per basket
                if chosen.count("FUEL01") > 1:
                    chosen = ["FUEL01"] + [c for c in chosen if c != "FUEL01"]
                lines = []
                for cat in chosen:
                    pool = live_by_cat.get(cat)
                    if not pool:
                        continue
                    m = rng.choices(pool, weights=[x["pop"] for x in pool])[0]
                    _name, tax_rate, cost_ratio = CATEGORIES[cat]
                    if cat == "FUEL01":
                        qty = round(min(max(rng.gauss(10.5, 4.0), 2.0), 28.0), 3)
                        unit = reg_price + FUEL_SPREAD[m["desc"]]
                        cost_ratio = cost_ratio * rng.uniform(0.98, 1.02)
                    else:
                        qty = rng.choices([1, 2, 3], weights=[88, 10, 2])[0]
                        unit = m["price"] * price_mult
                    net = round(qty * unit, 2)
                    lines.append({
                        "matnr": m["matnr"], "matkl": cat, "werks": s["werks"], "qty": qty,
                        "uom": m["uom"], "net": net, "cost": round(net * cost_ratio, 2),
                        "tax": round(net * tax_rate, 2),
                    })
                if not lines:
                    continue
                hhmmss = f"{h:02d}{rng.randint(0, 59):02d}{rng.randint(0, 59):02d}"
                vbeln = next_vbeln()
                r = rng.random()
                if r < CANCEL_RATE:
                    # Original is flagged cancelled; an S1 doc reverses it the same day
                    write_doc(vbeln, "ZPOS", day, hhmmss, lines, fksto="X")
                    write_doc(next_vbeln(), "S1", day, hhmmss, lines, sfakn=vbeln)
                else:
                    write_doc(vbeln, "ZPOS", day, hhmmss, lines)
                    if r < CANCEL_RATE + RETURN_RATE:
                        # Return a single non-fuel line 1-10 days later
                        ret = [l for l in lines if l["matkl"] != "FUEL01"]
                        if ret:
                            pending.append((day + timedelta(days=rng.randint(1, 10)),
                                            s["werks"], [rng.choice(ret)]))

        # Flush returns due today
        due = [p for p in pending if p[0] == day]
        pending = [p for p in pending if p[0] > day]
        for _d, _w, ret_lines in due:
            hhmmss = f"{rng.randint(9, 20):02d}{rng.randint(0, 59):02d}{rng.randint(0, 59):02d}"
            write_doc(next_vbeln(), "ZRET", day, hhmmss, ret_lines)

        day += timedelta(days=1)

    fk.close()
    fp.close()
    return n_head, n_line


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--start", default="2024-01-01", help="first business day (YYYY-MM-DD)")
    ap.add_argument("--end", default="2025-12-31", help="last business day (YYYY-MM-DD)")
    ap.add_argument("--baskets", type=float, default=1.0,
                    help="average baskets per store per hour (default 1.0, about 0.7M line items)")
    ap.add_argument("--out", default=str(Path.home() / "sap_raw"),
                    help="output folder (default: sap_raw in your home folder, e.g. C:\\Users\\<you>\\sap_raw)")
    ap.add_argument("--seed", type=int, default=42, help="random seed for repeatable output")
    # parse_known_args ignores extra arguments that Jupyter/IPython passes in
    # (e.g. --f=...kernel.json), so this also runs inside a notebook cell.
    args, _unknown = ap.parse_known_args()

    start, end = date.fromisoformat(args.start), date.fromisoformat(args.end)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    rng = random.Random(args.seed)

    materials = build_materials(rng, start, end)
    write_master_data(out, rng, materials)
    n_head, n_line = generate_sales(out, rng, materials, start, end, args.baskets)

    print(f"Wrote {len(STORES)} stores, {len(materials)} materials, "
          f"{n_head:,} billing headers, {n_line:,} line items to {out.resolve()}")


if __name__ == "__main__":
    main()
