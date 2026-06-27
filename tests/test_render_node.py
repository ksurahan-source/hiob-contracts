"""Hephaestus 순수 노드(RenderJobRequest.to_dispatch / RenderJobResponse.from_render_result)."""
from hiob_contracts.planet_envelopes import RenderJobRequest, RenderJobResponse


def test_to_dispatch_gates_unapproved_final():
    req = RenderJobRequest(render_job_id="rj1", run_id="run1", mode="final", approved_final_render=False)
    d = req.to_dispatch()
    assert d["renderJobId"] == "rj1"
    assert d["gated"] is True            # 승인 안 된 final = 게이트

    ok = RenderJobRequest(render_job_id="rj2", run_id="run1", mode="final", approved_final_render=True)
    assert ok.to_dispatch()["gated"] is False


def test_from_render_result_typed():
    resp = RenderJobResponse.from_render_result("rj1", {
        "success": True, "snapshotId": "snap9", "outputUrl": "https://r2/x.mp4",
    })
    assert isinstance(resp, RenderJobResponse)
    assert resp.render_status == "completed"
    assert resp.output_url.endswith(".mp4")
    assert resp.error is None


def test_from_render_result_failure():
    resp = RenderJobResponse.from_render_result("rj1", {"error": "lambda timeout"})
    assert resp.render_status == "failed"
    assert resp.error == {"reason": "lambda timeout"}
