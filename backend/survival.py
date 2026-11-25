from collections import Counter

def estimate(obs):
    times=Counter((row["seconds"],row["kind"]) for row in obs)
    active=len(obs)
    remaining=1
    curve=[]
    for second in sorted({t for t,_ in times}):
        arrived=times[second,"arrived"]
        censored=times[second,"censored"]
        remaining*=1-arrived/active
        curve.append({"seconds":second,"at_risk":active,"arrivals":arrived,
                      "censored":censored,"remaining":remaining})
        active-=arrived+censored
    return curve

def percentile(curve, fraction):
    return next((row["seconds"] for row in curve if row["remaining"]<=1-fraction),None)
