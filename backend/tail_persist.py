from drill_registry import drill
from survival import estimate,percentile

def read(cx,code):
    row=drill(cx,code)
    curve=cx.execute("SELECT * FROM muster_curves WHERE drill=%s ORDER BY seconds",(code,)).fetchall()
    return {"status":row["status"],"curve":curve,"median":percentile(curve,.5)}

def build_curve(cx,code):
    drill(cx,code,True)
    obs=cx.execute("SELECT seconds,kind FROM muster_clock WHERE drill=%s",(code,)).fetchall()
    for row in estimate(obs):
        cx.execute("""INSERT INTO muster_curves VALUES (%s,%(seconds)s,%(at_risk)s,%(arrivals)s,%(censored)s,%(remaining)s)""".replace("%s","%(drill)s",1),
          row|{"drill":code})
    cx.execute("UPDATE muster_drills SET status='calculated' WHERE code=%s",(code,))
    return read(cx,code)
