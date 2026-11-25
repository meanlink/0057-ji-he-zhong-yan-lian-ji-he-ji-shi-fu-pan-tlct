from tail_persist import build_curve

def seed(cx):
    for code,title,day,cutoff,full in [
        ('JR-11','松桥暖厅 11 月集合记录','2026-11-09',180,True),
        ('JR-12','西院值守记录试表','2026-11-02',120,False),
        ('JR-07','走廊活动室 10 月归档','2026-10-17',180,True),
    ]:
        if not cx.execute("""INSERT INTO muster_drills(code,title,day,cutoff)
           VALUES(%s,%s,%s,%s) ON CONFLICT DO NOTHING RETURNING code""",(code,title,day,cutoff)).fetchone():
            continue
        details=[('S-01','暖厅志愿组',60,'arrived'),('S-02','暖厅志愿组',120,'arrived'),
                 ('S-03','值守排班组',120,'arrived'),('S-04','联络组',cutoff,'censored')]
        for member,group,seconds,kind in details:
            cx.execute("INSERT INTO muster_members VALUES (%s,%s,%s)",(code,member,group))
            if full or member=='S-01':
                cx.execute("INSERT INTO muster_clock VALUES (%s,%s,%s,%s)",(code,member,seconds,kind))
        if code=='JR-07':
            build_curve(cx,code)
            cx.execute("INSERT INTO muster_followup VALUES (%s,'S-04','reviewer@demo.local','核对签入装置在观测截止时的记录。')",(code,))
