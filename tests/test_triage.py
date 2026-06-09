"""Tests for rule-based trace triage."""

from siha.harness.triage import TraceTriage


def _trace(status="success", tool_calls=None, steps=None, error_summary=None):
    return {
        "task": {"status": status, "error_summary": error_summary},
        "tool_calls": tool_calls or [],
        "steps": steps or [],
    }


def test_healthy_trace_needs_no_llm():
    trace = _trace(
        tool_calls=[{"success": True, "result": {"output": "done"}}],
        steps=[{"content": {"source": "template"}}],
    )
    critique = TraceTriage().triage(trace)
    assert critique is not None
    assert critique["triage"] == "healthy"
    assert critique["proposed_mutations"] == []
    assert any("template layer" in w for w in critique["what_went_well"])


def test_missing_file_classified():
    trace = _trace(
        status="failed",
        tool_calls=[{
            "success": False,
            "result": {"error": "cat: notes.txt: No such file or directory"},
        }],
    )
    critique = TraceTriage().triage(trace)
    assert critique is not None
    assert "missing_path" in critique["failure_categories"]


def test_safety_block_classified():
    trace = _trace(
        status="failed",
        tool_calls=[{
            "success": False,
            "result": {"error": "Blocked unsafe command (privilege escalation): 'sudo rm -rf /'"},
        }],
    )
    critique = TraceTriage().triage(trace)
    assert critique is not None
    assert "safety_block" in critique["failure_categories"]


def test_step_budget_classified_from_error_summary():
    trace = _trace(
        status="failed",
        error_summary="Step budget (50) exhausted before completion.",
    )
    critique = TraceTriage().triage(trace)
    assert critique is not None
    assert "step_budget_exhausted" in critique["failure_categories"]


def test_unrecognized_failure_defers_to_llm():
    trace = _trace(
        status="failed",
        tool_calls=[{
            "success": False,
            "result": {"error": "segmentation fault in libfoo.so at 0xdeadbeef"},
        }],
    )
    assert TraceTriage().triage(trace) is None
