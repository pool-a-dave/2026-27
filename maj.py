#!/usr/bin/env python3
"""Va chercher les stats LNH de la saison en cours et ecrit stats.json."""
import datetime, json, os, urllib.request

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
with open(os.path.join(ici, "stats.json"), "w", encoding="utf-8") as f:
    json.dump(snap, f, separators=(",", ":"))
print("stats.json: {} joueurs, {} gardiens, {} equipes".format(len(sk), len(go), len(te)))
