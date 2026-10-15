"""Opt-in AI tool caches and logs. Chats and model weights are other modules."""

from __future__ import annotations

from windowscleaner.modules.ai_targets import cache_plans
from windowscleaner.modules.base import CleanModule, ModuleResult, OnlyIds, ProgressCb, Risk
from windowscleaner.modules.path_rows import clean_plans, scan_plans


class AiCachesModule(CleanModule):
    id = "ai_caches"
    label = "AI Caches & Logs"
    description = (
        "Local caches and logs for Cursor, Claude, Codex, Copilot, Windsurf, "
        "and similar tools, plus Ollama and LM Studio logs. Does not delete chats, "
        "model weights, logins, skills, or settings."
    )
    risk = Risk.SAFE
    requires_admin = False
    default_enabled = False

    def scan(self, progress: ProgressCb | None = None) -> ModuleResult:
        return scan_plans(self, cache_plans(), progress)

    def clean(
        self,
        *,
        dry_run: bool = False,
        progress: ProgressCb | None = None,
        only_ids: OnlyIds = None,
    ) -> ModuleResult:
        return clean_plans(
            self,
            cache_plans(),
            dry_run=dry_run,
            progress=progress,
            only_ids=only_ids,
        )
