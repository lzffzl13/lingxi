"""Prompt manager and A/B test manager tests."""

import json
from unittest.mock import patch

from app.prompt.ab_testing import ABTestManager, TestVariant as ABTestVariant
from app.prompt.prompt_manager import PromptManager, PromptVersion


class TestPromptManager:
    def test_add_version_sets_active_and_persists(self, tmp_path):
        manager = PromptManager(storage_dir=str(tmp_path))

        version = manager.add_version(
            name="system",
            template="hello {name}",
            description="initial",
            tags=["prod"],
        )

        assert version.name == "system"
        assert version.version == 1
        assert version.tags == ["prod"]
        assert version.hash
        assert manager.get_active("system") == version
        assert (tmp_path / "prompts.json").exists()
        assert (tmp_path / "active.json").exists()

    def test_add_version_can_skip_active(self, tmp_path):
        manager = PromptManager(storage_dir=str(tmp_path))

        version = manager.add_version("system", "template", set_active=False)

        assert manager.get_active("system") is None
        assert manager.get_version(version.id) == version

    def test_loads_existing_prompts_and_active_versions(self, tmp_path):
        prompt = PromptVersion(
            id="system_v1_abc",
            name="system",
            template="template",
            version=1,
            created_at="2026-01-01T00:00:00",
        )
        (tmp_path / "prompts.json").write_text(
            json.dumps({"system": [prompt.__dict__]}),
            encoding="utf-8",
        )
        (tmp_path / "active.json").write_text(
            json.dumps({"system": prompt.id}),
            encoding="utf-8",
        )

        manager = PromptManager(storage_dir=str(tmp_path))

        assert manager.get_active("system").id == prompt.id
        assert manager.get_all_versions("system")[0].template == "template"

    def test_set_active_and_rollback(self, tmp_path):
        manager = PromptManager(storage_dir=str(tmp_path))
        v1 = manager.add_version("system", "one")
        v2 = manager.add_version("system", "two")
        v3 = manager.add_version("system", "three")

        assert manager.set_active("system", v2.id) is True
        assert manager.get_active("system") == v2
        assert manager.set_active("system", "missing") is False

        rolled_back = manager.rollback("system", steps=1)
        assert rolled_back == v1
        assert manager.get_active("system") == v1

        assert manager.rollback("system", steps=1) is None
        assert manager.get_version(v3.id) == v3

    def test_rollback_handles_invalid_states(self, tmp_path):
        manager = PromptManager(storage_dir=str(tmp_path))
        manager.add_version("single", "one")

        assert manager.rollback("single") is None
        assert manager.rollback("missing") is None

        manager._active_versions["single"] = "missing"
        assert manager.rollback("single") is None

    def test_update_metrics_and_stats(self, tmp_path):
        manager = PromptManager(storage_dir=str(tmp_path))
        version = manager.add_version("system", "template")

        manager.update_metrics(version.id, {"latency": 1.2, "success": 3})
        manager.update_metrics("missing", {"ignored": True})

        assert manager.get_version(version.id).metrics == {"latency": 1.2, "success": 3}
        stats = manager.get_stats()
        assert stats["total_prompts"] == 1
        assert stats["total_versions"] == 1
        assert stats["prompts"]["system"]["active"] == version.id


class TestABTestManager:
    def test_create_test_persists_variants(self, tmp_path):
        manager = ABTestManager(storage_dir=str(tmp_path))

        test = manager.create_test(
            name="Greeting",
            variants=[
                {"name": "A", "prompt_version_id": "p1", "weight": 2},
                {"name": "B", "prompt_version_id": "p2"},
            ],
        )

        assert test.name == "Greeting"
        assert len(test.variants) == 2
        assert test.variants[0].weight == 2
        assert manager.get_test(test.id) == test
        assert (tmp_path / "tests.json").exists()

    def test_load_tests_from_disk(self, tmp_path):
        manager = ABTestManager(storage_dir=str(tmp_path))
        test = manager.create_test(
            name="Loadable",
            variants=[{"name": "A", "prompt_version_id": "p1"}],
        )

        loaded = ABTestManager(storage_dir=str(tmp_path))

        assert loaded.get_test(test.id).name == "Loadable"
        assert loaded.get_test(test.id).variants[0].name == "A"

    def test_select_variant_requires_active_test(self, tmp_path):
        manager = ABTestManager(storage_dir=str(tmp_path))
        test = manager.create_test(
            name="Selection",
            variants=[{"name": "A", "prompt_version_id": "p1", "weight": 1}],
        )

        with patch("app.prompt.ab_testing.random.choices", return_value=[test.variants[0]]):
            assert manager.select_variant(test.id) == test.variants[0]

        assert manager.pause_test(test.id) is True
        assert manager.select_variant(test.id) is None
        assert manager.select_variant("missing") is None

    def test_select_variant_uses_random_choice_when_weights_are_zero(self, tmp_path):
        manager = ABTestManager(storage_dir=str(tmp_path))
        test = manager.create_test(
            name="Zero weights",
            variants=[
                {"name": "A", "prompt_version_id": "p1", "weight": 0},
                {"name": "B", "prompt_version_id": "p2", "weight": 0},
            ],
        )

        with patch("app.prompt.ab_testing.random.choice", return_value=test.variants[1]):
            assert manager.select_variant(test.id) == test.variants[1]

    def test_record_call_and_results(self, tmp_path):
        manager = ABTestManager(storage_dir=str(tmp_path))
        test = manager.create_test(
            name="Metrics",
            variants=[{"name": "A", "prompt_version_id": "p1"}],
        )
        variant = test.variants[0]

        manager.record_call(test.id, variant.id, success=True, latency=0.5, tokens=100)
        manager.record_call(test.id, variant.id, success=False, latency=1.0, tokens=50)
        manager.record_call("missing", variant.id, True, 1.0)
        manager.record_call(test.id, "missing", True, 1.0)

        results = manager.get_results(test.id)
        assert results["best_variant"]["variant_id"] == variant.id
        assert results["variants"][0]["total_calls"] == 2
        assert results["variants"][0]["success_rate"] == 0.5
        assert results["variants"][0]["avg_latency"] == 0.75
        assert results["variants"][0]["avg_tokens"] == 75.0
        assert manager.get_results("missing") is None

    def test_pause_resume_complete_and_stats(self, tmp_path):
        manager = ABTestManager(storage_dir=str(tmp_path))
        test = manager.create_test(
            name="Lifecycle",
            variants=[{"name": "A", "prompt_version_id": "p1"}],
        )

        assert manager.get_active_tests() == [test]
        assert manager.pause_test(test.id) is True
        assert test.status == "paused"
        assert manager.resume_test(test.id) is True
        assert test.status == "active"
        assert manager.complete_test(test.id) is True
        assert test.status == "completed"

        assert manager.pause_test("missing") is False
        assert manager.resume_test("missing") is False
        assert manager.complete_test("missing") is False

        stats = manager.get_stats()
        assert stats["total_tests"] == 1
        assert stats["active_tests"] == 0
        assert stats["total_calls"] == 0


def test_test_variant_defaults_metrics():
    variant = ABTestVariant(id="v1", name="A", prompt_version_id="p1")

    assert variant.metrics == {
        "total_calls": 0,
        "success_count": 0,
        "total_latency": 0.0,
        "total_tokens": 0,
    }
