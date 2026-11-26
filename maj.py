#!/usr/bin/env python3
"""Va chercher les stats LNH de la saison en cours et ecrit stats.json."""
import datetime, json, os, re, urllib.request
from concurrent.futures import ThreadPoolExecutor

API = ("https://api.nhle.com/stats/rest/en/{}/summary?start={}&limit=100"
       "&sort=%5B%7B%22property%22:%22playerId%22,%22direction%22:%22ASC%22%7D%5D"
       "&cayenneExp=seasonId={}%20and%20gameTypeId=2")
API_EQ = "https://api.nhle.com/stats/rest/en/team/summary?limit=100&cayenneExp=seasonId={}%20and%20gameTypeId=2"

def saison():
    d = datetime.date.today()
    debut = d.year if d.month >= 9 else d.year - 1
    return "{}{}".format(debut, debut + 1)

def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "pool-hockey/1.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))

def tous(kind, s):
    out, start = [], 0
    while True:
        rep = get(API.format(kind, start, s))
        out += rep["data"]
        start += len(rep["data"])
        if not rep["data"] or start >= rep.get("total", 0):
            return out

s = saison()
sk, go, te = tous("skater", s), tous("goalie", s), get(API_EQ.format(s))["data"]
if not sk or not te:
    raise SystemExit("Reponse LNH vide, stats.json garde tel quel")
snap = {
    "fetched_at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
    "season": s,
    "skaters": {str(p["playerId"]): [p["gamesPlayed"], p["goals"], p["assists"]] for p in sk},
    "goalies": {str(p["playerId"]): [p["gamesPlayed"], p["wins"], p["losses"], p["otLosses"] or 0,
                                      p["shutouts"], p["goals"], p["assists"]] for p in go},
    "teams": {str(t["teamId"]): [t["gamesPlayed"], t["wins"], t["losses"], t["otLosses"] or 0, t["points"]] for t in te},
}
ici = os.path.dirname(os.path.abspath(__file__))

# Absences : dernier match de chaque joueur du pool et matchs joues par son equipe depuis.
def absences():
    html = open(os.path.join(ici, "index.html"), encoding="utf-8").read()
    pool = json.loads(re.search(r"window\.POOL = (.*?);\s*/\*FIN_DONNEES", html, re.S).group(1))
    ids = [p["id"] for p in pool["roster"] if p["cat"] in ("F", "D", "G")]
    web = "https://api-web.nhle.com/v1/"
    with ThreadPoolExecutor(8) as ex:
        fiches = dict(zip(ids, ex.map(lambda i: get(web + "player/{}/landing".format(i)), ids)))
    equipes = {f.get("currentTeamAbbrev") for f in fiches.values() if f.get("currentTeamAbbrev")}
    with ThreadPoolExecutor(8) as ex:
        cal = dict(zip(equipes, ex.map(lambda t: get(web + "club-schedule-season/{}/{}".format(t, s))["games"], equipes)))
    fini = {t: sorted(g["gameDate"] for g in gs if g.get("gameType") == 2 and g.get("gameState") in ("FINAL", "OFF"))
            for t, gs in cal.items()}
    # Les matchs d'aujourd'hui (heure de l'Est) ne comptent pas encore : les fiches des joueurs
    # sont mises a jour plus lentement que le calendrier.
    hier = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=5)).date().isoformat()
    fini = {t: [d for d in ds if d < hier] for t, ds in fini.items()}
    out = {}
    for i, f in fiches.items():
        t = f.get("currentTeamAbbrev")
        if t not in fini:
            continue
        joues = sorted(g["gameDate"] for g in f.get("last5Games", []) if g.get("gameTypeId", 2) == 2)
        dernier = joues[-1] if joues else None
        manques = sum(1 for d in fini[t] if dernier is None or d > dernier)
        out[str(i)] = [dernier, manques, t]
    return out

try:
    snap["absences"] = absences()
except Exception as e:
    print("Absences non disponibles:", e)
with open(os.path.join(ici, "stats.json"), "w", encoding="utf-8") as f:
    json.dump(snap, f, separators=(",", ":"))
print("stats.json: {} joueurs, {} gardiens, {} equipes".format(len(sk), len(go), len(te)))
