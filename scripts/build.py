"""
Builds the two phone lists the POS "Identify Phone" button searches:

  tacdb.json   IMEI model codes (TAC = first 8 digits of an IMEI) -> phone,
               from the open MoazEb/tac-database list (MIT licence).
  devices.json Every Android model number certified for Google Play -> phone,
               from Google's official "supported devices" list.

Run by .github/workflows/update.yml every week. A list is only replaced when
its download worked and still holds at least 80% of the phones it had, so a
broken or half-downloaded source never wipes the list the POS uses.
Standard library only.
"""
import csv, io, json, os, re, sys, urllib.request, collections, datetime, hashlib

TAC_URL = 'https://raw.githubusercontent.com/MoazEb/tac-database/main/tac_full.csv'
GOOGLE_URL = 'https://storage.googleapis.com/play_public/supported_devices.csv'
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TODAY = datetime.date.today().isoformat()

SPECIAL = {'IPHONE': 'iPhone', 'IPAD': 'iPad', 'IPOD': 'iPod', 'OPPO': 'Oppo', 'ONEPLUS': 'OnePlus', 'IQOO': 'iQOO',
           'POCO': 'Poco', 'REDMI': 'Redmi', 'XL': 'XL', 'SE': 'SE', 'FE': 'FE', 'II': 'II', 'III': 'III', 'TV': 'TV',
           'USB': 'USB', 'LTE': 'LTE', 'NFC': 'NFC', 'ZTE': 'ZTE', 'LG': 'LG', 'HTC': 'HTC', 'TCL': 'TCL', 'HMD': 'HMD',
           'BLU': 'BLU', 'CAT': 'CAT'}
SERIES = re.compile(r'^(RENO|NOTE|MATE|NOVA|PURA|EDGE|PIXEL|XPERIA|MOTO|FIND|ZENFONE|NARZO|SPARK|CAMON|POVA|HOT|MAGIC|PLAY|ACE|NORD|ARMOR)(\d+[A-Z]*)$')


def nice(s):
    """'SAMSUNG GALAXY S24 ULTRA' -> 'Samsung Galaxy S24 Ultra'"""
    out = []
    for w in s.split():
        u = w.upper()
        if u in SPECIAL:
            out.append(SPECIAL[u])
        elif SERIES.match(u):
            g = re.match(r'^([A-Z]+)(\d+[A-Z]*)$', u)
            out.append(g.group(1).capitalize() + g.group(2))
        elif re.search(r'\d', w):
            out.append(u)
        else:
            out.append('-'.join(p[:1].upper() + p[1:].lower() for p in w.split('-')))
    return ' '.join(out)


def fetch(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'phone-list-updater'})
    with urllib.request.urlopen(req, timeout=180) as r:
        return r.read()


# ── IMEI model codes ────────────────────────────────────────────────────────
YEAR = re.compile(r'^(199\d|20[0-3]\d)$')
GLUED = re.compile(r'^(.*[A-Za-z].*?)(199\d|20[0-3]\d)$')
CODE = re.compile(r'^[A-Z0-9][A-Z0-9\-/_.]{2,}$')
VARIANT = re.compile(r'\bmodel\b|version|edition|dual|global|china|india|europe|\bUS\b|telstra|optus|vodafone|boost|\bAU\b|australia', re.I)


def is_code(w):
    return bool(CODE.match(w)) and bool(re.search(r'\d', w)) and bool(re.search(r'[A-Z]', w))


def build_tac(text):
    names, nlist, models, mlist, tacmap = {}, [], {}, [], {}

    def nidx(n):
        if n not in names:
            names[n] = len(nlist)
            nlist.append(n)
        return names[n]

    rows = csv.reader(io.StringIO(text))
    next(rows, None)
    for row in rows:
        if len(row) < 3:
            continue
        b, tac, spec = row[0], row[1], row[2]
        tac = re.sub(r'\D', '', tac)
        if not tac or len(tac) > 8:
            continue
        tac = tac.zfill(8)
        brand = b.strip().upper()
        year, toks = '', []
        for x in (x.strip() for x in spec.split(',')):
            if not x:
                continue
            if YEAR.match(x):
                year = year or x
                continue
            if x.upper() in ('N/A', 'TEST DEVICE'):
                continue
            toks.append(x)
        if not toks:
            continue
        name, rest = toks[0], toks[1:]
        if name.upper() == brand and rest:
            name = rest.pop(0)
        clean = []
        for x in rest:
            ws = x.split()
            if ws:
                g = GLUED.match(ws[-1])
                if g and len(ws[-1]) > 5:
                    year = year or g.group(2)
                    ws[-1] = g.group(1)
            clean.append(' '.join(ws))
        name_words = set(name.upper().split())
        codes = []
        for x in clean:
            for w in x.split():
                wu = w.upper()
                if wu == w and is_code(wu) and wu not in name_words and wu not in codes:
                    codes.append(wu)
        nw = name.upper().split()
        if len(nw) == 2 and is_code(nw[1]):                 # "OPPO CPH2811" -> use the marketing name listed with it
            for x in clean:
                xw = x.upper().split()
                if len(xw) >= 2 and xw[0] == nw[0] and not all(is_code(w) for w in xw[1:]):
                    if nw[1] not in codes:
                        codes.insert(0, nw[1])
                    name = x
                    break
        details = []
        for x in clean:
            if not x or x.upper() == name.upper():
                continue
            ws = x.split()
            if len(ws) <= 3 and all(is_code(w.upper()) or w.upper() == ws[0].upper() for w in ws):
                continue
            if not VARIANT.search(x):
                continue
            if x not in details:
                details.append(x)
        key = (nidx(nice(name)), ' '.join(codes), '; '.join(details), int(year or 0))
        if key not in models:
            models[key] = len(mlist)
            mlist.append(key)
        tacmap[tac] = models[key]

    def b36(n):
        s, o = '0123456789abcdefghijklmnopqrstuvwxyz', ''
        while True:
            n, r = divmod(n, 36)
            o = s[r] + o
            if not n:
                return o

    parts, prev = [], 0
    for t, i in sorted((int(t), i) for t, i in tacmap.items()):
        parts.append(b36(t - prev) + '.' + b36(i))
        prev = t
    return {'v': 1, 'src': 'MoazEb/tac-database (MIT)', 'count': len(tacmap),
            'N': nlist, 'M': [list(k) for k in mlist], 'T': ' '.join(parts)}


# ── Google Play supported devices ───────────────────────────────────────────
def build_google(raw):
    for enc in ('utf-16', 'utf-8-sig', 'latin-1'):
        try:
            text = raw.decode(enc)
            if 'Marketing Name' in text[:400]:
                break
        except UnicodeDecodeError:
            continue
    rows = csv.reader(io.StringIO(text))
    head = next(rows, [])
    col = {h.strip(): i for i, h in enumerate(head)}
    ib, iname, imodel = col.get('Retail Branding', 0), col.get('Marketing Name', 1), col.get('Model', 3)
    brands, blist = {}, []
    group = collections.OrderedDict()
    for r in rows:
        if len(r) <= max(ib, iname, imodel):
            continue
        brand = re.sub(r'\s+', ' ', r[ib]).strip()
        name = re.sub(r'\s+', ' ', r[iname].replace('&amp;', '&').replace('\\t', ' ')).strip()
        model = re.sub(r'\s+', ' ', r[imodel]).strip()
        if not model or not (brand or name):
            continue
        if not name:
            name = model
        nb = nice(brand) if brand and (brand.islower() or brand.isupper()) else brand   # 'motorola' / 'OPPO' -> 'Motorola' / 'Oppo'
        if brand and name.lower().startswith(brand.lower()):
            full = nb + name[len(brand):]
        elif brand:
            full = nb + ' ' + name
        else:
            full = name
        if brand not in brands:
            brands[brand] = len(blist)
            blist.append(brand)
        key = (brands[brand], full)
        codes = group.setdefault(key, [])
        mu = model.upper()
        if mu not in codes:
            codes.append(mu)
    R = [[b, n, '|'.join(c)] for (b, n), c in group.items()]
    return {'v': 1, 'src': 'Google Play supported devices', 'count': sum(len(r[2].split('|')) for r in R),
            'B': blist, 'R': R}


# ── write only when something changed ───────────────────────────────────────
def write(fname, data):
    path = os.path.join(ROOT, fname)
    old = None
    if os.path.exists(path):
        try:
            with open(path, encoding='utf-8') as f:
                old = json.load(f)
        except Exception:
            old = None
    if old and old.get('count') and data['count'] < 0.8 * old['count']:
        print(f'{fname}: only {data["count"]} entries vs {old["count"]} before, keeping the old list', file=sys.stderr)
        return False
    body = {k: v for k, v in data.items()}
    sig = hashlib.sha1(json.dumps(body, sort_keys=True).encode()).hexdigest()
    if old and old.get('sig') == sig:
        print(f'{fname}: no change')
        return False
    body['sig'] = sig
    body['built'] = TODAY
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(body, f, separators=(',', ':'), ensure_ascii=False)
    print(f'{fname}: {data["count"]} entries written')
    return True


def main():
    ok = True
    try:
        src = sys.argv[1] if len(sys.argv) > 1 else None
        text = open(src, encoding='utf-8', errors='replace').read() if src else fetch(TAC_URL).decode('utf-8', 'replace')
        write('tacdb.json', build_tac(text))
    except Exception as e:
        ok = False
        print('IMEI list failed:', e, file=sys.stderr)
    try:
        src = sys.argv[2] if len(sys.argv) > 2 else None
        raw = open(src, 'rb').read() if src else fetch(GOOGLE_URL)
        write('devices.json', build_google(raw))
    except Exception as e:
        ok = False
        print('Google list failed:', e, file=sys.stderr)
    with open(os.path.join(ROOT, 'last-checked.txt'), 'w') as f:
        f.write(TODAY + ('' if ok else ' (one list could not be downloaded; kept the previous one)') + '\n')


if __name__ == '__main__':
    main()
