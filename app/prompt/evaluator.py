"""Prompt evaluation system."""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional, Callable
from dataclasses import dataclass, asdict

from app.utils.logger import logger


@dataclass
class EvaluationResult:
    """Result of a prompt evaluation."""
    prompt_version_id: str
    test_case_id: str
    score: float
    latency: float
    token_usage: int
    feedback: str = ""
    metadata: dict = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


@dataclass
class TestCase:
    """A test case for prompt evaluation."""
    id: str
    input_text: str
    expected_output: str = ""
    context: str = ""
    category: str = "general"
    metadata: dict = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class PromptEvaluator:
    """Evaluate prompt performance.

    Features:
    - Test case management
    - Automated evaluation
    - Scoring metrics
    - Comparison reports
    """

    def __init__(self, storage_dir: str = "./data/evaluations"):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self._test_cases: dict[str, TestCase] = {}
        self._results: list[EvaluationResult] = []
        self._evaluator_func: Optional[Callable] = None

        # Load existing data
        self._load_data()

    def _load_data(self) -> None:
        """Load test cases and results from storage."""
        # Load test cases
        cases_file = self.storage_dir / "test_cases.json"
        if cases_file.exists():
            try:
                with open(cases_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for case_data in data.values():
                    case = TestCase(**case_data)
                    self._test_cases[case.id] = case
                logger.info(f"Loaded {len(self._test_cases)} test cases")
            except Exception as e:
                logger.error(f"Failed to load test cases: {e}")

        # Load results
        results_file = self.storage_dir / "results.json"
        if results_file.exists():
            try:
                with open(results_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._results = [EvaluationResult(**r) for r in data]
                logger.info(f"Loaded {len(self._results)} evaluation results")
            except Exception as e:
                logger.error(f"Failed to load results: {e}")

    def _save_data(self) -> None:
        """Save test cases and results to storage."""
        # Save test cases
        cases_file = self.storage_dir / "test_cases.json"
        data = {k: asdict(v) for k, v in self._test_cases.items()}
        with open(cases_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        # Save results
        results_file = self.storage_dir / "results.json"
        with open(results_file, "w", encoding="utf-8") as f:
            json.dump([asdict(r) for r in self._results], f, ensure_ascii=False, indent=2)

    def set_evaluator(self, evaluator_func: Callable) -> None:
        """Set the evaluator function.

        The function should accept (prompt, input, expected_output) and return a score (0-1).
        """
        self._evaluator_func = evaluator_func

    def add_test_case(
        self,
        case_id: str,
        input_text: str,
        expected_output: str = "",
        context: str = "",
        category: str = "general",
        metadata: Optional[dict] = None,
    ) -> TestCase:
        """Add a test case."""
        case = TestCase(
            id=case_id,
            input_text=input_text,
            expected_output=expected_output,
            context=context,
            category=category,
            metadata=metadata or {},
        )
        self._test_cases[case_id] = case
        self._save_data()

        logger.info(f"Added test case: {case_id}")
        return case

    def add_test_cases_batch(self, cases: list[dict]) -> int:
        """Add multiple test cases.

        Args:
            cases: List of dicts with test case fields

        Returns:
            Number of cases added
        """
        count = 0
        for case_data in cases:
            case_id = case_data.get("id") or f"case_{len(self._test_cases) + 1}"
            self.add_test_case(case_id=case_id, **case_data)
            count += 1

        return count

    def get_test_cases(self, category: Optional[str] = None) -> list[TestCase]:
        """Get test cases, optionally filtered by category."""
        cases = list(self._test_cases.values())
        if category:
            cases = [c for c in cases if c.category == category]
        return cases

    async def evaluate_prompt(
        self,
        prompt_version_id: str,
        prompt_template: str,
        llm_func: Callable,
        test_case_ids: Optional[list[str]] = None,
        category: Optional[str] = None,
    ) -> dict:
        """Evaluate a prompt against test cases.

        Args:
            prompt_version_id: ID of the prompt version being evaluated
            prompt_template: The prompt template to evaluate
            llm_func: Async function to call LLM (accepts messages, returns response)
            test_case_ids: Specific test cases to use (None for all)
            category: Filter test cases by category

        Returns:
            Evaluation summary
        """
        # Get test cases
        if test_case_ids:
            cases = [self._test_cases[cid] for cid in test_case_ids if cid in self._test_cases]
        else:
            cases = self.get_test_cases(category)

        if not cases:
            return {"error": "No test cases available"}

        results = []
        for case in cases:
            try:
                # Build messages
                messages = [
                    {"role": "system", "content": prompt_template},
                    {"role": "user", "content": case.input_text},
                ]

                # Call LLM
                start_time = datetime.now()
                response = await llm_func(messages)
                latency = (datetime.now() - start_time).total_seconds()

                # Extract response content
                if hasattr(response, 'choices'):
                    output = response.choices[0].message.content
                    tokens = response.usage.total_tokens if response.usage else 0
                else:
                    output = str(response)
                    tokens = 0

                # Calculate score
                if self._evaluator_func:
                    score = await self._evaluator_func(
                        prompt=prompt_template,
                        input_text=case.input_text,
                        expected_output=case.expected_output,
                        actual_output=output,
                    )
                else:
                    # Simple scoring based on output length and keyword matching
                    score = self._simple_score(output, case.expected_output)

                # Record result
                result = EvaluationResult(
                    prompt_version_id=prompt_version_id,
                    test_case_id=case.id,
                    score=score,
                    latency=latency,
                    token_usage=tokens,
                    metadata={"output": output[:200]},
                )
                results.append(result)
                self._results.append(result)

            except Exception as e:
                logger.error(f"Failed to evaluate test case {case.id}: {e}")
                results.append(EvaluationResult(
                    prompt_version_id=prompt_version_id,
                    test_case_id=case.id,
                    score=0.0,
                    latency=0.0,
                    token_usage=0,
                    feedback=str(e),
                ))

        # Save results
        self._save_data()

        # Calculate summary
        summary = self._calculate_summary(prompt_version_id, results)
        return summary

    def _simple_score(self, output: str, expected: str) -> float:
        """Simple scoring based on output characteristics."""
        if not expected:
            # No expected output, score based on output quality
            if len(output) > 10:
                return 0.7
            return 0.3

        # Keyword matching
        expected_keywords = set(expected.lower().split())
        output_keywords = set(output.lower().split())

        if not expected_keywords:
            return 0.5

        overlap = len(expected_keywords & output_keywords)
        score = overlap / len(expected_keywords)

        return min(1.0, score)

    def _calculate_summary(self, prompt_version_id: str, results: list[EvaluationResult]) -> dict:
        """Calculate evaluation summary."""
        if not results:
            return {"error": "No results"}

        scores = [r.score for r in results]
        latencies = [r.latency for r in results]
        tokens = [r.token_usage for r in results]

        return {
            "prompt_version_id": prompt_version_id,
            "total_cases": len(results),
            "avg_score": sum(scores) / len(scores),
            "min_score": min(scores),
            "max_score": max(scores),
            "avg_latency": sum(latencies) / len(latencies),
            "avg_tokens": sum(tokens) / len(tokens),
            "pass_rate": len([s for s in scores if s >= 0.7]) / len(scores),
        }

    def compare_prompts(self, version_ids: list[str]) -> dict:
        """Compare multiple prompt versions.

        Args:
            version_ids: List of prompt version IDs to compare

        Returns:
            Comparison report
        """
        comparisons = {}
        for version_id in version_ids:
            version_results = [r for r in self._results if r.prompt_version_id == version_id]
            if version_results:
                scores = [r.score for r in version_results]
                latencies = [r.latency for r in version_results]
                comparisons[version_id] = {
                    "total_evaluations": len(version_results),
                    "avg_score": sum(scores) / len(scores),
                    "avg_latency": sum(latencies) / len(latencies),
                    "pass_rate": len([s for s in scores if s >= 0.7]) / len(scores),
                }

        # Find best version
        if comparisons:
            best_version = max(comparisons.items(), key=lambda x: x[1]["avg_score"])
            comparisons["best_version"] = best_version[0]

        return comparisons

    def get_stats(self) -> dict:
        """Get evaluator statistics."""
        return {
            "total_test_cases": len(self._test_cases),
            "total_evaluations": len(self._results),
            "categories": list(set(c.category for c in self._test_cases.values())),
        }


# Global evaluator instance
_evaluator: Optional[PromptEvaluator] = None


def get_evaluator() -> PromptEvaluator:
    """Get global evaluator instance."""
    global _evaluator
    if _evaluator is None:
        _evaluator = PromptEvaluator()
    return _evaluator
