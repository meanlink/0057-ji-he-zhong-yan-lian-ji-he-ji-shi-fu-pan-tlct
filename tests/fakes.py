"""测试专用基座：在没有 Postgres/Redis 的环境里，用内存假件驱动后端业务模块。

不修改 /workspace/backend 任何代码，只在 sys.modules 里注入 core / psycopg /
fastapi 等依赖的最小替身。假件实现的语义只覆盖本仓库 SQL 实际用到的部分。
"""
import sys
import types
from datetime import datetime, timezone
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND))


# ---------- psycopg 替身 ----------
class _Row(dict):
    """dict_row 风格：既支持列名访问，又支持 | 合并。"""


def _row(mapping):
    return _Row(mapping)


class IntegrityError(Exception):
    pass


class Jsonb:
    def __init__(self, value, dumps=None):
        self.value = value


psycopg_mod = types.ModuleType("psycopg")
psycopg_mod.IntegrityError = IntegrityError
psycopg_mod.connect = None

rows_mod = types.ModuleType("psycopg.rows")
rows_mod.dict_row = object()
json_mod = types.ModuleType("psycopg.types.json")
json_mod.Jsonb = Jsonb
psycopg_mod.rows = rows_mod
psycopg_mod.types = types.SimpleNamespace(json=json_mod)

sys.modules["psycopg"] = psycopg_mod
sys.modules["psycopg.rows"] = rows_mod
sys.modules["psycopg.types"] = psycopg_mod.types
sys.modules["psycopg.types.json"] = json_mod


# ---------- fastapi 替身 ----------
class HTTPException(Exception):
    def __init__(self, status_code, detail):
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"{status_code}: {detail}")


class _Depends:
    def __call__(self, *args, **kwargs):
        return None


class APIRouter:
    def __init__(self, prefix=""):
        self.prefix = prefix

    def include_router(self, other):
        pass

    def _route(self, *_args, **_kwargs):
        def deco(fn):
            return fn
        return deco

    get = post = put = delete = _route


fastapi_mod = types.ModuleType("fastapi")
fastapi_mod.APIRouter = APIRouter
fastapi_mod.Depends = _Depends()
fastapi_mod.HTTPException = HTTPException

security_mod = types.ModuleType("fastapi.security")
security_mod.HTTPBearer = object
security_mod.HTTPAuthorizationCredentials = object
fastapi_mod.security = security_mod

pydantic_mod = types.ModuleType("pydantic")


class BaseModel:
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)

    def model_dump(self):
        return dict(self.__dict__)


class _FieldInfo:
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs


def Field(*args, **kwargs):
    return _FieldInfo(*args, **kwargs)


pydantic_mod.BaseModel = BaseModel
pydantic_mod.Field = Field

encoders_mod = types.ModuleType("fastapi.encoders")
encoders_mod.jsonable_encoder = lambda x: x

sys.modules["fastapi"] = fastapi_mod
sys.modules["fastapi.security"] = security_mod
sys.modules["pydantic"] = pydantic_mod
sys.modules["fastapi.encoders"] = encoders_mod


# ---------- jwt / redis 替身（core 导入时需要） ----------
jwt_mod = types.ModuleType("jwt")
jwt_mod.encode = lambda payload, secret, algorithm: "token"
jwt_mod.decode = lambda *a, **k: {}
jwt_mod.InvalidTokenError = type("InvalidTokenError", (Exception,), {})
sys.modules["jwt"] = jwt_mod

redis_mod = types.ModuleType("redis")


class _Redis:
    @classmethod
    def from_url(cls, *a, **k):
        return cls()

    def ping(self):
        return True


redis_mod.Redis = _Redis
sys.modules["redis"] = redis_mod


# ---------- core 替身：复用真实 enqueue/db 契约，换成内存库 ----------
core_mod = types.ModuleType("core")
core_mod.ROLES = ("operator", "reviewer", "viewer")
core_mod.JOB_STATES = ("queued", "running", "done", "failed")
core_mod.SECRET = "test-secret"
core_mod.ISSUER = "test"
core_mod.AUTH = object()
core_mod.CACHE = _Redis()
core_mod.BUSINESS_PATH = "/api"
core_mod.HTTPException = HTTPException
core_mod.Jsonb = Jsonb


class _JobSeq:
    value = 0

    @classmethod
    def next(cls):
        cls.value += 1
        return cls.value


def enqueue(connection, kind, payload, *, available_at=None):
    job_id = _JobSeq.next()
    connection.tables["app_jobs"].append(_row({
        "id": job_id, "kind": kind, "payload": payload,
        "status": "queued", "result": None, "error": None,
        "available_at": datetime.now(timezone.utc),
        "created_at": datetime.now(timezone.utc), "finished_at": None,
    }))
    return job_id


core_mod.enqueue = enqueue


class _DbCtx:
    def __init__(self, fake):
        self.fake = fake

    def __enter__(self):
        return self.fake

    def __exit__(self, *exc):
        return False


def db():
    return _DbCtx(FAKE)


core_mod.db = db


def require(*roles):
    def _dep(credentials=None):
        return {"email": "reviewer@demo.local", "role": "reviewer"}
    return _dep


core_mod.require = require
core_mod.password_hash = lambda *a, **k: "hash"
core_mod.token_for = lambda u: "token"
core_mod.initialize = lambda *a, **k: None
core_mod.seed_users = lambda *a, **k: None

sys.modules["core"] = core_mod


# ---------- 内存数据库 ----------
class Transaction:
    def __init__(self, fake):
        self.fake = fake
        self.snapshot = None

    def __enter__(self):
        import copy
        self.snapshot = copy.deepcopy(self.fake.tables)
        return self

    def __exit__(self, exc_type, exc, tb):
        if exc_type is not None:
            self.fake.tables = self.snapshot
        return False


class FakeCursor:
    def __init__(self, fake, rows=None):
        self.fake = fake
        self._rows = rows or []

    def fetchone(self):
        return self._rows[0] if self._rows else None

    def fetchall(self):
        return self._rows


class FakeDB:
    """按 SQL 特征字符串分派的最小内存实现，覆盖仓库全部语句。"""

    def __init__(self):
        self.tables = {
            "muster_drills": [],
            "muster_members": [],
            "muster_clock": [],
            "muster_curves": [],
            "muster_followup": [],
            "muster_corrections": [],
            "app_jobs": [],
        }
        self._correction_seq = 0

    def transaction(self):
        return Transaction(self)

    # 测试辅助
    def seed_drill(self, code="JR-11", cutoff=180, status="calculated",
                   observations=None):
        self.tables["muster_drills"].append(_row({
            "code": code, "title": "测试窗", "day": "2026-11-09",
            "cutoff": cutoff, "status": status,
        }))
        if observations is None:
            observations = [
                ("S-01", 60, "arrived"), ("S-02", 120, "arrived"),
                ("S-03", 120, "arrived"), ("S-04", cutoff, "censored"),
            ]
        for code2, seconds, kind in observations:
            self.tables["muster_members"].append(
                _row({"drill": code, "code": code2, "group_name": "G"}))
            self.tables["muster_clock"].append(
                _row({"drill": code, "code": code2, "seconds": seconds, "kind": kind}))

    def execute(self, sql, params=None):
        params = params or ()
        s = " ".join(sql.split())
        t = self.tables

        # ---- 演练行 ----
        if s.startswith("SELECT * FROM muster_drills WHERE code="):
            locked = "FOR UPDATE" in s
            rows = [r for r in t["muster_drills"] if r["code"] == params[0]]
            return FakeCursor(self, rows)
        if "UPDATE muster_drills SET status='sealed'" in s:
            for r in t["muster_drills"]:
                if r["code"] == params[0]:
                    r["status"] = "sealed"
            return FakeCursor(self)
        if "UPDATE muster_drills SET status='calculated'" in s:
            for r in t["muster_drills"]:
                if r["code"] == params[0]:
                    r["status"] = "calculated"
            return FakeCursor(self)

        # ---- 封存时检查缺录（须在名册 JOIN 分支之前匹配） ----
        if "SELECT count(*) AS missing FROM muster_members" in s:
            code = params[0]
            member_codes = {(m["drill"], m["code"]) for m in t["muster_members"]
                            if m["drill"] == code}
            clock_codes = {(c["drill"], c["code"]) for c in t["muster_clock"]
                           if c["drill"] == code}
            return FakeCursor(self, [_Row({"missing": len(member_codes - clock_codes)})])

        # ---- 名册 ----
        if "FROM muster_members m LEFT JOIN muster_clock" in s:
            code = params[0]
            out = []
            for m in t["muster_members"]:
                if m["drill"] != code:
                    continue
                clock = next((c for c in t["muster_clock"]
                              if c["drill"] == m["drill"] and c["code"] == m["code"]), None)
                out.append(_Row({**m, "seconds": clock["seconds"] if clock else None,
                                 "kind": clock["kind"] if clock else None}))
            return FakeCursor(self, sorted(out, key=lambda r: (r["group_name"], r["code"])))
        if "SELECT 1 FROM muster_members WHERE drill=" in s:
            hit = any(m["drill"] == params[0] and m["code"] == params[1]
                      for m in t["muster_members"])
            return FakeCursor(self, [_Row({"1": 1})] if hit else [])

        # ---- 签到原件 ----
        if s.startswith("SELECT seconds,kind FROM muster_clock WHERE drill="):
            rows = [_Row({"seconds": c["seconds"], "kind": c["kind"]})
                    for c in t["muster_clock"] if c["drill"] == params[0]]
            return FakeCursor(self, rows)
        if s.startswith("SELECT kind FROM muster_clock WHERE drill="):
            hit = next((c for c in t["muster_clock"]
                        if c["drill"] == params[0] and c["code"] == params[1]), None)
            return FakeCursor(self, [_Row({"kind": hit["kind"]})] if hit else [])
        if s.startswith("SELECT code,seconds,kind FROM muster_clock WHERE drill="):
            rows = [_Row({"code": c["code"], "seconds": c["seconds"], "kind": c["kind"]})
                    for c in sorted((c for c in t["muster_clock"]
                                     if c["drill"] == params[0]),
                                    key=lambda r: r["code"])]
            return FakeCursor(self, rows)
        if s.startswith("DELETE FROM muster_clock WHERE drill="):
            t["muster_clock"] = [c for c in t["muster_clock"]
                                 if c["drill"] != params[0]]
            return FakeCursor(self)
        if s.startswith("INSERT INTO muster_clock"):
            drill_c, code, seconds, kind = params
            existing = next((c for c in t["muster_clock"]
                             if c["drill"] == drill_c and c["code"] == code), None)
            if existing is not None:
                existing["seconds"] = seconds
                existing["kind"] = kind
            else:
                t["muster_clock"].append(
                    _Row({"drill": drill_c, "code": code,
                          "seconds": seconds, "kind": kind}))
            return FakeCursor(self)

        # ---- 曲线 ----
        if s.startswith("SELECT * FROM muster_curves WHERE drill="):
            rows = [r for r in t["muster_curves"] if r["drill"] == params[0]]
            return FakeCursor(self, sorted(rows, key=lambda r: r["seconds"]))
        if s.startswith("DELETE FROM muster_curves WHERE drill="):
            t["muster_curves"] = [r for r in t["muster_curves"]
                                  if r["drill"] != params[0]]
            return FakeCursor(self)
        if s.startswith("INSERT INTO muster_curves"):
            t["muster_curves"].append(_Row(dict(params)))
            return FakeCursor(self)

        # ---- 补查单 ----
        if s.startswith("SELECT * FROM muster_followup WHERE drill="):
            rows = [r for r in t["muster_followup"] if r["drill"] == params[0]]
            return FakeCursor(self, sorted(rows, key=lambda r: r["code"]))
        if s.startswith("SELECT code FROM muster_followup WHERE drill="):
            rows = [_Row({"code": r["code"]}) for r in t["muster_followup"]
                    if r["drill"] == params[0]]
            return FakeCursor(self, sorted(rows, key=lambda r: r["code"]))
        if s.startswith("INSERT INTO muster_followup"):
            t["muster_followup"].append(
                _Row({"drill": params[0], "code": params[1],
                      "owner": params[2], "action": params[3]}))
            return FakeCursor(self, list(t["muster_followup"][-1:]))

        # ---- 更正单 ----
        if "FROM muster_corrections c JOIN app_jobs" in s:
            rows = []
            for c in t["muster_corrections"]:
                if c["drill"] != params[0]:
                    continue
                job = next(j for j in t["app_jobs"] if j["id"] == c["job_id"])
                rows.append(_Row({**c, "job_state": job["status"], "job_error": job["error"]}))
            return FakeCursor(self, sorted(rows, key=lambda r: r["id"]))
        if "SELECT id FROM muster_corrections WHERE drill=" in s:
            rows = [_Row({"id": c["id"]}) for c in t["muster_corrections"]
                    if c["drill"] == params[0] and c["status"] in params[1]]
            return FakeCursor(self, rows)
        if s.startswith("SELECT * FROM muster_corrections WHERE id="):
            rows = [c for c in t["muster_corrections"]
                    if c["id"] == params[0] and c["drill"] == params[1]]
            return FakeCursor(self, rows)
        if s.startswith("INSERT INTO muster_corrections"):
            self._correction_seq += 1
            now = datetime.now(timezone.utc)
            row = _Row({
                "id": self._correction_seq, "drill": params[0], "owner": params[1],
                "reason": params[2],
                "observations": params[3].value if isinstance(params[3], Jsonb) else params[3],
                "baseline": params[4].value if isinstance(params[4], Jsonb) else params[4],
                "status": "queued", "detail": None, "job_id": params[5],
                "created_at": now, "updated_at": now,
            })
            t["muster_corrections"].append(row)
            return FakeCursor(self, [row])
        if "UPDATE app_jobs SET payload=" in s:
            payload = params[0].value if isinstance(params[0], Jsonb) else params[0]
            for j in t["app_jobs"]:
                if j["id"] == params[1]:
                    j["payload"] = payload
            return FakeCursor(self)
        if "UPDATE muster_corrections SET status='running'" in s:
            for c in t["muster_corrections"]:
                if c["id"] == params[0]:
                    c["status"] = "running"
                    c["updated_at"] = datetime.now(timezone.utc)
            return FakeCursor(self)
        if "UPDATE muster_corrections SET status='returned'" in s:
            for c in t["muster_corrections"]:
                if c["id"] == params[1]:
                    c["status"] = "returned"
                    c["detail"] = params[0]
                    c["updated_at"] = datetime.now(timezone.utc)
            return FakeCursor(self)
        if "UPDATE muster_corrections SET status='effective'" in s:
            for c in t["muster_corrections"]:
                if c["id"] == params[0]:
                    c["status"] = "effective"
                    c["detail"] = None
                    c["updated_at"] = datetime.now(timezone.utc)
            return FakeCursor(self)
        if "UPDATE muster_corrections SET status='queued',detail=NULL" in s:
            for c in t["muster_corrections"]:
                if c["id"] == params[1]:
                    c["status"] = "queued"
                    c["detail"] = None
                    c["job_id"] = params[0]
                    c["updated_at"] = datetime.now(timezone.utc)
            return FakeCursor(self, [c for c in t["muster_corrections"]
                                     if c["id"] == params[1]])
        if "SET status='failed', detail=" in s:
            for c in t["muster_corrections"]:
                if c["id"] == params[1] and c["status"] in ("queued", "running"):
                    c["status"] = "failed"
                    c["detail"] = params[0]
                    c["updated_at"] = datetime.now(timezone.utc)
            return FakeCursor(self)

        # ---- 后台任务 ----
        if s.startswith("SELECT id,kind,payload FROM app_jobs"):
            queued = [j for j in t["app_jobs"] if j["status"] == "queued"]
            return FakeCursor(self, queued[:1])
        if "UPDATE app_jobs SET status='running' WHERE id=" in s:
            for j in t["app_jobs"]:
                if j["id"] == params[0]:
                    j["status"] = "running"
            return FakeCursor(self)
        if "UPDATE app_jobs SET status='done'" in s:
            result = params[0].value if isinstance(params[0], Jsonb) else params[0]
            for j in t["app_jobs"]:
                if j["id"] == params[1]:
                    j["status"] = "done"
                    j["result"] = result
                    j["finished_at"] = datetime.now(timezone.utc)
            return FakeCursor(self)
        if "UPDATE app_jobs SET status='failed'" in s:
            for j in t["app_jobs"]:
                if j["id"] == params[1]:
                    j["status"] = "failed"
                    j["error"] = params[0]
                    j["finished_at"] = datetime.now(timezone.utc)
            return FakeCursor(self)

        raise AssertionError(f"FakeDB 未实现的 SQL: {s}")


FAKE = FakeDB()
