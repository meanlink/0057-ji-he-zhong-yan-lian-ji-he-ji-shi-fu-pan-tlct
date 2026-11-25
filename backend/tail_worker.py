from tail_persist import build_curve

def run(cx,kind,data):
    if kind != "estimate_muster_tail":
        raise ValueError(kind)
    return build_curve(cx,data["drill"])
