"""Opt-in AI model weights. Every row starts unchecked and needs an extra confirm."""

from __future__ import annotations

from windowscleaner.modules.ai_targets import model_plans
from windowscleaner.modules.base import CleanModule, ModuleResult, OnlyIds, ProgressCb, Risk
from windowscleaner.modules.path_rows import clean_plans, scan_plans


class AiModelsModule(CleanModule):
    id = "ai_models"
    label = "AI Model Weights"
    description = (
        "Ollama and LM Studio downloaded weights. Rows start unchecked. "
        "Deleting them means downloading the models again. The apps stay installed."
    )
    risk = Risk.AGGRESSIVE
    requires_admin = False
    default_enabled = False

    def scan(self, progress: ProgressCb | None = None) -> ModuleResult:
        return scan_plans(self, model_plans(), progress)

    def clean(
        self,
        *,
        dry_run: bool = False,
        progress: ProgressCb | None = None,
        only_ids: OnlyIds = None,
        include_unchecked: bool = False,
    ) -> ModuleResult:
        return clean_plans(
            self,
            model_plans(),
            dry_run=dry_run,
            progress=progress,
            only_ids=only_ids,
            include_unchecked=include_unchecked,
        )
