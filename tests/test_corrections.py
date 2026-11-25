"""需求级端到端测试：用内存假件跑通更正、并发、重试与切换全流程。

运行：python3 -I tests/test_corrections.py
"""
import copy
import sys
import unittest
from unittest import mock

import fakes
from fakes import FAKE, Jsonb, HTTPException

import correction_log
import correction_worker
import domain
import followup_log
import tail_persist
import worker
from correction_input import Correction, CorrectionObservation
from survival import estimate


def obs(code, seconds, kind):
    return CorrectionObservation(code=code, seconds=seconds, kind=kind)


def correction(reason, items):
    return Correction(reason=reason, observations=items)


def build_published_curve(cx, code="JR-11"):
    """模拟曲线发布：由真实 build_curve 生成 muster_curves。"""
    return tail_persist.build_curve(cx, code)


def run_next_job(cx):
    return worker.process(cx)


def reset():
    fakes._JobSeq.value = 0
    fakes.FAKE = fakes.FakeDB()
    fakes.core_mod.db = lambda: fakes._DbCtx(fakes.FAKE)
    # 让所有模块共享同一个假件
    for name in list(sys.modules):
        if name.startswith(("correction", "tail", "followup", "seal", "survival",
                            "drill", "clock", "domain", "worker")):
            sys.modules.pop(name, None)


class CorrectionFlowTests(unittest.TestCase):
    def setUp(self):
        reset()
        self.cx = fakes.FAKE
        self.cx.seed_drill()
        build_published_curve(self.cx)
        self.reviewer = "reviewer@demo.local"

    def _open(self, items=None, reason="签到原件抄录有误，按卷内原件更正"):
        if items is None:
            # 把 S-04 由"截止未签到"更正为 90 秒签到
            items = [obs("S-01", 60, "arrived"), obs("S-02", 120, "arrived"),
                     obs("S-03", 120, "arrived"), obs("S-04", 90, "arrived")]
        return correction_log.open_correction(
            self.cx, "JR-11", correction(reason, items), self.reviewer)

    # 需求 1：曲线发布后复核员可发起更正
    def test_open_only_after_calculated(self):
        self.cx.tables["muster_drills"][0]["status"] = "sealed"
        with self.assertRaises(HTTPException) as ctx:
            self._open()
        self.assertEqual(ctx.exception.status_code, 409)
        self.assertIn("曲线发布后", ctx.exception.detail)

    def test_open_requires_full_roster_observations(self):
        items = [obs("S-01", 60, "arrived"), obs("S-02", 120, "arrived"),
                 obs("S-03", 120, "arrived")]  # 缺 S-04
        with self.assertRaises(HTTPException) as ctx:
            self._open(items)
        self.assertIn("缺少 1 位", ctx.exception.detail)

    def test_open_rejects_unknown_code(self):
        items = [obs("S-01", 60, "arrived"), obs("S-02", 120, "arrived"),
                 obs("S-03", 120, "arrived"), obs("X-99", 180, "censored")]
        with self.assertRaises(HTTPException) as ctx:
            self._open(items)
        self.assertIn("不在本轮名册", ctx.exception.detail)

    def test_open_rejects_censored_not_at_cutoff(self):
        items = [obs("S-01", 60, "arrived"), obs("S-02", 120, "arrived"),
                 obs("S-03", 120, "arrived"), obs("S-04", 100, "censored")]
        with self.assertRaises(HTTPException) as ctx:
            self._open(items)
        self.assertIn("截止时刻", ctx.exception.detail)

    def test_open_rejects_duplicate_code(self):
        items = [obs("S-01", 60, "arrived"), obs("S-01", 90, "arrived"),
                 obs("S-02", 120, "arrived"), obs("S-03", 120, "arrived")]
        with self.assertRaises(HTTPException) as ctx:
            self._open(items)
        self.assertIn("重复记录码", ctx.exception.detail)

    # 需求 2：重算时仍能查原曲线、按原记录开补查
    def test_original_curve_and_followup_available_while_queued(self):
        before = tail_persist.read(self.cx, "JR-11")
        opened = self._open()
        # 更正单已在途，但曲线与原件未切换
        during = tail_persist.read(self.cx, "JR-11")
        self.assertEqual(before["curve"], during["curve"])
        self.assertEqual(during["status"], "calculated")
        ticket = opened["ticket"]
        self.assertEqual(ticket["status"], "queued")
        # 基线快照保留了原曲线和原签到原件
        self.assertEqual(len(ticket["baseline"]["curve"]), len(before["curve"]))
        self.assertEqual({r["code"] for r in ticket["baseline"]["clock"]},
                         {"S-01", "S-02", "S-03", "S-04"})
        # 仍可按原记录（S-04 仍为 censored）开补查
        from followup_input import Followup
        row = followup_log.collect_followup(
            self.cx, "JR-11", Followup(code="S-04", action="核对签到装置记录。"),
            self.reviewer)
        self.assertEqual(row["code"], "S-04")

    # 需求 3：更正生效时曲线和补查资格一次性切换
    def test_effective_switches_curve_and_eligibility_atomically(self):
        self._open()
        result = run_next_job(self.cx)
        self.assertTrue(result)
        tail = tail_persist.read(self.cx, "JR-11")
        # 新曲线：S-04 在 90 秒到达，90 秒时刻在险 2、到达 1
        step90 = next(r for r in tail["curve"] if r["seconds"] == 90)
        self.assertEqual(step90["arrivals"], 1)
        # 4 人在险，60 秒先走 1 人，90 秒时刻在险为 3
        self.assertEqual(step90["at_risk"], 3)
        # 已无 censored 原件 -> 补查资格整体变化
        kinds = {r["code"]: r["kind"] for r in self.cx.tables["muster_clock"]}
        self.assertTrue(all(k == "arrived" for k in kinds.values()))
        # 更正单状态
        ticket = self.cx.tables["muster_corrections"][0]
        self.assertEqual(ticket["status"], "effective")
        # job 已完成且结果可读
        job = self.cx.tables["app_jobs"][-1]
        self.assertEqual(job["status"], "done")
        self.assertEqual(job["result"]["outcome"], "effective")

    def test_no_censored_means_followup_rejected_after_switch(self):
        self._open()
        run_next_job(self.cx)
        from followup_input import Followup
        with self.assertRaises(HTTPException) as ctx:
            followup_log.collect_followup(
                self.cx, "JR-11", Followup(code="S-04", action="核对签到装置记录。"),
                self.reviewer)
        self.assertEqual(ctx.exception.status_code, 409)

    # 需求 4：更正与开单并发，补查单先开成 -> 更正退回，原曲线继续有效
    def test_returned_when_followup_wins_race(self):
        original_curve = copy.deepcopy(self.cx.tables["muster_curves"])
        self._open()
        # 并发场景：补查单在重算前先开成（S-04 更正后将变为 arrived，构成阻断）
        from followup_input import Followup
        followup_log.collect_followup(
            self.cx, "JR-11", Followup(code="S-04", action="先一步开立的补查。"),
            self.reviewer)
        run_next_job(self.cx)
        ticket = self.cx.tables["muster_corrections"][0]
        self.assertEqual(ticket["status"], "returned")
        self.assertIn("S-04", ticket["detail"])
        # 原曲线继续有效，原件未被替换
        self.assertEqual(self.cx.tables["muster_curves"], original_curve)
        s04 = next(c for c in self.cx.tables["muster_clock"] if c["code"] == "S-04")
        self.assertEqual(s04["kind"], "censored")
        # job 业务上正常结束（done，outcome=returned），不是技术失败
        job = self.cx.tables["app_jobs"][-1]
        self.assertEqual(job["status"], "done")
        self.assertEqual(job["result"]["outcome"], "returned")

    def test_non_blocking_followup_does_not_return(self):
        # S-02 补查单与更正无冲突：更正后 S-02 仍是 arrived，本来就开不了单；
        # 改为把 S-04 保持 censored，同时对 S-04 开单 —— 更正后仍 censored，不阻断。
        items = [obs("S-01", 60, "arrived"), obs("S-02", 100, "arrived"),
                 obs("S-03", 120, "arrived"), obs("S-04", 180, "censored")]
        self._open(items)
        from followup_input import Followup
        followup_log.collect_followup(
            self.cx, "JR-11", Followup(code="S-04", action="与更正不冲突的补查。"),
            self.reviewer)
        run_next_job(self.cx)
        ticket = self.cx.tables["muster_corrections"][0]
        self.assertEqual(ticket["status"], "effective")
        # 既有补查单保留
        self.assertTrue(any(f["code"] == "S-04"
                            for f in self.cx.tables["muster_followup"]))

    # 需求 5：重算失败后能重试同一张更正单
    def test_retry_same_ticket_after_failure(self):
        opened = self._open()
        ticket_id = opened["ticket"]["id"]
        # 注入一次业务失败（HTTPException 的 detail 会被 worker 透传）
        with mock.patch.object(correction_worker, "drill",
                               side_effect=HTTPException(500, "boom")):
            run_next_job(self.cx)
        ticket = self.cx.tables["muster_corrections"][0]
        self.assertEqual(ticket["status"], "failed")
        self.assertIn("boom", ticket["detail"])
        # 同一张单重试，不新建更正单
        retried = correction_log.retry_correction(self.cx, "JR-11", ticket_id)
        self.assertEqual(retried["ticket"]["id"], ticket_id)
        self.assertEqual(retried["ticket"]["status"], "queued")
        self.assertEqual(len(self.cx.tables["muster_corrections"]), 1)
        # 重试后成功，曲线切换
        run_next_job(self.cx)
        self.assertEqual(self.cx.tables["muster_corrections"][0]["status"],
                         "effective")

    def test_returned_ticket_can_retry_after_followup_cleared(self):
        self._open()
        from followup_input import Followup
        followup_log.collect_followup(
            self.cx, "JR-11", Followup(code="S-04", action="先一步开立的补查。"),
            self.reviewer)
        run_next_job(self.cx)
        ticket_id = self.cx.tables["muster_corrections"][0]["id"]
        self.assertEqual(self.cx.tables["muster_corrections"][0]["status"],
                         "returned")
        # 复核处理掉阻断单（测试中直接移除），重试同一张单
        self.cx.tables["muster_followup"].clear()
        correction_log.retry_correction(self.cx, "JR-11", ticket_id)
        run_next_job(self.cx)
        self.assertEqual(self.cx.tables["muster_corrections"][0]["status"],
                         "effective")

    # 需求 6：已生效的更正重试不重复发布
    def test_effective_ticket_cannot_be_requeued(self):
        self._open()
        run_next_job(self.cx)
        ticket_id = self.cx.tables["muster_corrections"][0]["id"]
        jobs_before = len(self.cx.tables["app_jobs"])
        with self.assertRaises(HTTPException) as ctx:
            correction_log.retry_correction(self.cx, "JR-11", ticket_id)
        self.assertEqual(ctx.exception.status_code, 409)
        self.assertIn("已生效", ctx.exception.detail)
        self.assertEqual(len(self.cx.tables["app_jobs"]), jobs_before)

    def test_worker_idempotent_on_duplicate_delivery(self):
        self._open()
        run_next_job(self.cx)
        curve_after = copy.deepcopy(self.cx.tables["muster_curves"])
        # 模拟同一 payload 被重复投递
        job = self.cx.tables["app_jobs"][-1]
        outcome = domain.run_job(self.cx, "correct_muster_tail", job["payload"])
        self.assertEqual(outcome["outcome"], "already_effective")
        self.assertEqual(self.cx.tables["muster_curves"], curve_after)

    # 在途单互斥
    def test_only_one_in_flight_ticket_per_drill(self):
        self._open()
        with self.assertRaises(HTTPException) as ctx:
            self._open()
        self.assertEqual(ctx.exception.status_code, 409)
        self.assertIn("在途更正单", ctx.exception.detail)

    def test_can_open_again_after_effective(self):
        self._open()
        run_next_job(self.cx)
        second = self._open(reason="二次核对后再次更正")
        self.assertEqual(second["ticket"]["id"], 2)
        run_next_job(self.cx)
        statuses = [c["status"] for c in self.cx.tables["muster_corrections"]]
        self.assertEqual(statuses, ["effective", "effective"])

    # 重试边界
    def test_retry_unknown_ticket_404(self):
        with self.assertRaises(HTTPException) as ctx:
            correction_log.retry_correction(self.cx, "JR-11", 999)
        self.assertEqual(ctx.exception.status_code, 404)

    def test_retry_queued_ticket_rejected(self):
        opened = self._open()
        with self.assertRaises(HTTPException) as ctx:
            correction_log.retry_correction(self.cx, "JR-11",
                                            opened["ticket"]["id"])
        self.assertEqual(ctx.exception.status_code, 409)

    # 曲线数值正确性：与 survival.estimate 一致
    def test_rebuilt_curve_matches_km_estimate(self):
        items = [obs("S-01", 60, "arrived"), obs("S-02", 120, "arrived"),
                 obs("S-03", 120, "arrived"), obs("S-04", 90, "arrived")]
        self._open(items)
        run_next_job(self.cx)
        expected = estimate([{"seconds": o.seconds, "kind": o.kind} for o in items])
        actual = [dict(r) for r in self.cx.tables["muster_curves"]]
        self.assertEqual(len(actual), len(expected))
        for got, want in zip(actual, expected):
            self.assertEqual(got["seconds"], want["seconds"])
            self.assertEqual(got["at_risk"], want["at_risk"])
            self.assertEqual(got["arrivals"], want["arrivals"])
            self.assertAlmostEqual(got["remaining"], want["remaining"])

    # 进度查询
    def test_list_corrections_joins_job_state(self):
        self._open()
        rows = correction_log.list_corrections(self.cx, "JR-11")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["job_state"], "queued")
        run_next_job(self.cx)
        rows = correction_log.list_corrections(self.cx, "JR-11")
        self.assertEqual(rows[0]["job_state"], "done")
        self.assertEqual(rows[0]["status"], "effective")


if __name__ == "__main__":
    unittest.main(verbosity=2)
