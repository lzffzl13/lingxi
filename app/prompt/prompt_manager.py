"""Prompt version management system."""

import json
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, asdict

from app.utils.logger import logger


@dataclass
class PromptVersion:
    """A versioned prompt template."""
    id: str
    name: str
    template: str
    version: int
    created_at: str
    description: str = ""
    tags: list[str] = None
    metrics: dict = None

    def __post_init__(self):
        if self.tags is None:
            self.tags = []
        if self.metrics is None:
            self.metrics = {}

    @property
    def hash(self) -> str:
        """Get content hash of the template."""
        return hashlib.md5(self.template.encode()).hexdigest()[:8]


class PromptManager:
    """Manage prompt versions with history and rollback.

    Features:
    - Version tracking
    - Rollback support
    - A/B testing integration
    - Performance metrics
    """

    def __init__(self, storage_dir: str = "./data/prompts"):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self._prompts: dict[str, list[PromptVersion]] = {}
        self._active_versions: dict[str, str] = {}  # name -> version_id

        # Load existing prompts
        self._load_prompts()

    def _load_prompts(self) -> None:
        """Load prompts from storage."""
        prompts_file = self.storage_dir / "prompts.json"
        if not prompts_file.exists():
            return

        try:
            with open(prompts_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            for name, versions in data.items():
                self._prompts[name] = [
                    PromptVersion(**v) for v in versions
                ]

            # Load active versions
            active_file = self.storage_dir / "active.json"
            if active_file.exists():
                with open(active_file, "r", encoding="utf-8") as f:
                    self._active_versions = json.load(f)

            logger.info(f"Loaded {len(self._prompts)} prompt families")
        except Exception as e:
            logger.error(f"Failed to load prompts: {e}")

    def _save_prompts(self) -> None:
        """Save prompts to storage."""
        prompts_file = self.storage_dir / "prompts.json"

        data = {}
        for name, versions in self._prompts.items():
            data[name] = [asdict(v) for v in versions]

        with open(prompts_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        # Save active versions
        active_file = self.storage_dir / "active.json"
        with open(active_file, "w", encoding="utf-8") as f:
            json.dump(self._active_versions, f, ensure_ascii=False)

    def add_version(
        self,
        name: str,
        template: str,
        description: str = "",
        tags: Optional[list[str]] = None,
        set_active: bool = True,
    ) -> PromptVersion:
        """Add a new prompt version.

        Args:
            name: Prompt name (e.g., "system_prompt")
            template: Prompt template text
            description: Version description
            tags: Optional tags for categorization
            set_active: Whether to set this as active version

        Returns:
            The created PromptVersion
        """
        if name not in self._prompts:
            self._prompts[name] = []

        # Calculate next version number
        existing_versions = self._prompts[name]
        next_version = len(existing_versions) + 1

        # Create version ID
        version_id = f"{name}_v{next_version}_{hashlib.md5(template.encode()).hexdigest()[:6]}"

        # Create prompt version
        prompt_version = PromptVersion(
            id=version_id,
            name=name,
            template=template,
            version=next_version,
            created_at=datetime.now().isoformat(),
            description=description,
            tags=tags or [],
        )

        # Add to versions
        self._prompts[name].append(prompt_version)

        # Set as active if requested
        if set_active:
            self._active_versions[name] = version_id

        # Save to disk
        self._save_prompts()

        logger.info(f"Added prompt version: {version_id}")
        return prompt_version

    def get_active(self, name: str) -> Optional[PromptVersion]:
        """Get the active version of a prompt."""
        if name not in self._active_versions:
            return None

        version_id = self._active_versions[name]
        return self.get_version(version_id)

    def get_version(self, version_id: str) -> Optional[PromptVersion]:
        """Get a specific prompt version by ID."""
        for versions in self._prompts.values():
            for version in versions:
                if version.id == version_id:
                    return version
        return None

    def get_all_versions(self, name: str) -> list[PromptVersion]:
        """Get all versions of a prompt."""
        return self._prompts.get(name, [])

    def set_active(self, name: str, version_id: str) -> bool:
        """Set a specific version as active."""
        # Verify version exists
        version = self.get_version(version_id)
        if not version:
            return False

        self._active_versions[name] = version_id
        self._save_prompts()

        logger.info(f"Set active prompt: {name} -> {version_id}")
        return True

    def rollback(self, name: str, steps: int = 1) -> Optional[PromptVersion]:
        """Rollback to a previous version.

        Args:
            name: Prompt name
            steps: Number of versions to roll back

        Returns:
            The new active version, or None if rollback fails
        """
        versions = self.get_all_versions(name)
        if len(versions) < 2:
            return None

        # Find current active version
        active_id = self._active_versions.get(name)
        if not active_id:
            return None

        current_idx = None
        for i, v in enumerate(versions):
            if v.id == active_id:
                current_idx = i
                break

        if current_idx is None:
            return None

        # Calculate target index
        target_idx = max(0, current_idx - steps)
        if target_idx == current_idx:
            return None

        # Set new active version
        target_version = versions[target_idx]
        self._active_versions[name] = target_version.id
        self._save_prompts()

        logger.info(f"Rolled back {name} from v{current_idx + 1} to v{target_idx + 1}")
        return target_version

    def update_metrics(self, version_id: str, metrics: dict) -> None:
        """Update metrics for a prompt version."""
        version = self.get_version(version_id)
        if version:
            version.metrics.update(metrics)
            self._save_prompts()

    def get_stats(self) -> dict:
        """Get prompt manager statistics."""
        total_versions = sum(len(v) for v in self._prompts.values())
        return {
            "total_prompts": len(self._prompts),
            "total_versions": total_versions,
            "active_versions": dict(self._active_versions),
            "prompts": {
                name: {
                    "versions": len(versions),
                    "active": self._active_versions.get(name),
                }
                for name, versions in self._prompts.items()
            },
        }


# Global prompt manager instance
_prompt_manager: Optional[PromptManager] = None


def get_prompt_manager() -> PromptManager:
    """Get global prompt manager instance."""
    global _prompt_manager
    if _prompt_manager is None:
        _prompt_manager = PromptManager()
    return _prompt_manager
