"""回归：封存、曲线计算、补查开立的既有链路在 worker/domain 改造后仍工作。"""
import unittest

import fakes
from fakes import FAKE, HTTPException

import domain
import followup_log
import seal_window
import tail_persist
import worker
from followup_input import Followup


class LegacyFlowTests(unittest.TestCase):
    def setUp(self):
        fakes._JobSeq.value = 0
        fakes.FAKE = fakes.FakeDB()
        self.cx = fakes.FAKE

    def test_seal_calculate_followup_chain(self):
        # open 状态、观测齐备
        self.cx.seed_drill(status="open")
        receipt = seal_window.seal(self.cx, "JR-11")
        self.assertEqual(self.cx.tables["muster_drills"][0]["status"], "sealed")
        self.assertTrue(worker.process(self.cx))
        job = self.cx.tables["app_jobs"][0]
        self.assertEqual(job["kind"], "estimate_muster_tail")
        self.assertEqual(job["status"], "done")
        self.assertEqual(self.cx.tables["muster_drills"][0]["status"],
                         "calculated")
        # 曲线已生成
        tail = tail_persist.read(self.cx, "JR-11")
        self.assertTrue(tail["curve"])
        # 对 censored 成员可开补查
        row = followup_log.collect_followup(
            self.cx, "JR-11",
            Followup(code="S-04", action="核对签入装置在观测截止时的记录。"),
            "reviewer@demo.local")
        self.assertEqual(row["code"], "S-04")
        # 对 arrived 成员开补查被拒绝
        with self.assertRaises(HTTPException):
            followup_log.collect_followup(
                self.cx, "JR-11",
                Followup(code="S-01", action="不应开立的补查。"),
                "reviewer@demo.local")

    def test_unknown_job_kind_fails_gracefully(self):
        self.cx.seed_drill(status="open")
        fakes.core_mod.enqueue(self.cx, "not_a_real_job", {"drill": "JR-11"})
        touched = worker.process(self.cx)
        self.assertTrue(touched)
        self.assertEqual(self.cx.tables["app_jobs"][0]["status"], "failed")

    def test_dispatch_unknown_kind_raises(self):
        self.cx.seed_drill()
        with self.assertRaises(ValueError):
            domain.run_job(self.cx, "nonsense", {})


if __name__ == "__main__":
    unittest.main(verbosity=2)
