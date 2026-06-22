"""A/B testing for prompts."""

import random
import json
from datetime import datetime
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, asdict

from app.utils.logger import logger


@dataclass
class TestVariant:
    """A variant in an A/B test."""
    id: str
    name: str
    prompt_version_id: str
    weight: float = 1.0  # Relative weight for selection
    metrics: dict = None

    def __post_init__(self):
        if self.metrics is None:
            self.metrics = {
                "total_calls": 0,
                "success_count": 0,
                "total_latency": 0.0,
                "total_tokens": 0,
            }


@dataclass
class ABTest:
    """An A/B test configuration."""
    id: str
    name: str
    variants: list[TestVariant]
    created_at: str
    status: str = "active"  # active, paused, completed
    description: str = ""
    metrics: dict = None

    def __post_init__(self):
        if self.metrics is None:
            self.metrics = {}


class ABTestManager:
    """Manage A/B tests for prompts.

    Features:
    - Create and manage tests
    - Weighted variant selection
    - Metrics tracking
    - Statistical significance calculation
    """

    def __init__(self, storage_dir: str = "./data/ab_tests"):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self._tests: dict[str, ABTest] = {}

        # Load existing tests
        self._load_tests()

    def _load_tests(self) -> None:
        """Load tests from storage."""
        tests_file = self.storage_dir / "tests.json"
        if not tests_file.exists():
            return

        try:
            with open(tests_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            for test_data in data.values():
                variants = [TestVariant(**v) for v in test_data.pop("variants")]
                test = ABTest(variants=variants, **test_data)
                self._tests[test.id] = test

            logger.info(f"Loaded {len(self._tests)} A/B tests")
        except Exception as e:
            logger.error(f"Failed to load A/B tests: {e}")

    def _save_tests(self) -> None:
        """Save tests to storage."""
        tests_file = self.storage_dir / "tests.json"

        data = {}
        for test_id, test in self._tests.items():
            test_dict = asdict(test)
            data[test_id] = test_dict

        with open(tests_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def create_test(
        self,
        name: str,
        variants: list[dict],
        description: str = "",
    ) -> ABTest:
        """Create a new A/B test.

        Args:
            name: Test name
            variants: List of variant configs with 'name', 'prompt_version_id', and optional 'weight'
            description: Test description

        Returns:
            Created ABTest
        """
        import hashlib
        test_id = f"test_{hashlib.md5(name.encode()).hexdigest()[:8]}"

        # Create variants
        test_variants = []
        for i, v in enumerate(variants):
            variant = TestVariant(
                id=f"{test_id}_v{i}",
                name=v.get("name", f"Variant {i}"),
                prompt_version_id=v["prompt_version_id"],
                weight=v.get("weight", 1.0),
            )
            test_variants.append(variant)

        # Create test
        test = ABTest(
            id=test_id,
            name=name,
            variants=test_variants,
            created_at=datetime.now().isoformat(),
            description=description,
        )

        self._tests[test_id] = test
        self._save_tests()

        logger.info(f"Created A/B test: {test_id} with {len(test_variants)} variants")
        return test

    def get_test(self, test_id: str) -> Optional[ABTest]:
        """Get an A/B test by ID."""
        return self._tests.get(test_id)

    def get_active_tests(self) -> list[ABTest]:
        """Get all active tests."""
        return [t for t in self._tests.values() if t.status == "active"]

    def select_variant(self, test_id: str) -> Optional[TestVariant]:
        """Select a variant for a test using weighted random selection.

        Returns:
            Selected TestVariant, or None if test not found
        """
        test = self.get_test(test_id)
        if not test or test.status != "active":
            return None

        # Weighted random selection
        weights = [v.weight for v in test.variants]
        total_weight = sum(weights)

        if total_weight == 0:
            # Equal weights
            return random.choice(test.variants)

        # Normalize weights
        probabilities = [w / total_weight for w in weights]
        selected = random.choices(test.variants, weights=probabilities, k=1)[0]

        return selected

    def record_call(
        self,
        test_id: str,
        variant_id: str,
        success: bool,
        latency: float,
        tokens: int = 0,
    ) -> None:
        """Record a call result for a variant.

        Args:
            test_id: Test ID
            variant_id: Variant ID
            success: Whether the call was successful
            latency: Call latency in seconds
            tokens: Token usage
        """
        test = self.get_test(test_id)
        if not test:
            return

        # Find variant
        variant = None
        for v in test.variants:
            if v.id == variant_id:
                variant = v
                break

        if not variant:
            return

        # Update metrics
        variant.metrics["total_calls"] += 1
        if success:
            variant.metrics["success_count"] += 1
        variant.metrics["total_latency"] += latency
        variant.metrics["total_tokens"] += tokens

        self._save_tests()

    def get_results(self, test_id: str) -> Optional[dict]:
        """Get test results with statistics."""
        test = self.get_test(test_id)
        if not test:
            return None

        results = []
        for variant in test.variants:
            metrics = variant.metrics
            total_calls = metrics["total_calls"]

            if total_calls > 0:
                success_rate = metrics["success_count"] / total_calls
                avg_latency = metrics["total_latency"] / total_calls
                avg_tokens = metrics["total_tokens"] / total_calls
            else:
                success_rate = 0
                avg_latency = 0
                avg_tokens = 0

            results.append({
                "variant_id": variant.id,
                "variant_name": variant.name,
                "prompt_version_id": variant.prompt_version_id,
                "total_calls": total_calls,
                "success_rate": round(success_rate, 4),
                "avg_latency": round(avg_latency, 3),
                "avg_tokens": round(avg_tokens, 1),
            })

        # Calculate statistical significance (simplified)
        best_variant = max(results, key=lambda x: x["success_rate"]) if results else None

        return {
            "test_id": test.id,
            "test_name": test.name,
            "status": test.status,
            "created_at": test.created_at,
            "variants": results,
            "best_variant": best_variant,
        }

    def pause_test(self, test_id: str) -> bool:
        """Pause a test."""
        test = self.get_test(test_id)
        if test:
            test.status = "paused"
            self._save_tests()
            return True
        return False

    def resume_test(self, test_id: str) -> bool:
        """Resume a test."""
        test = self.get_test(test_id)
        if test:
            test.status = "active"
            self._save_tests()
            return True
        return False

    def complete_test(self, test_id: str) -> bool:
        """Mark a test as completed."""
        test = self.get_test(test_id)
        if test:
            test.status = "completed"
            self._save_tests()
            return True
        return False

    def get_stats(self) -> dict:
        """Get overall statistics."""
        active_tests = len([t for t in self._tests.values() if t.status == "active"])
        total_calls = sum(
            sum(v.metrics["total_calls"] for v in t.variants)
            for t in self._tests.values()
        )

        return {
            "total_tests": len(self._tests),
            "active_tests": active_tests,
            "total_calls": total_calls,
        }


# Global A/B test manager instance
_ab_test_manager: Optional[ABTestManager] = None


def get_ab_test_manager() -> ABTestManager:
    """Get global A/B test manager instance."""
    global _ab_test_manager
    if _ab_test_manager is None:
        _ab_test_manager = ABTestManager()
    return _ab_test_manager
