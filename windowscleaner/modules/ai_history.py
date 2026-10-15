"""Opt-in local AI chats and sessions. Not selected by Full or Free disk."""

from __future__ import annotations

from windowscleaner.modules.ai_targets import history_plans
from windowscleaner.modules.base import CleanModule, ModuleResult, OnlyIds, ProgressCb, Risk
from windowscleaner.modules.path_rows import clean_plans, scan_plans


class AiHistoryModule(CleanModule):
    id = "ai_history"
    label = "AI Chats & Sessions"
    description = (
        "Local chat transcripts and session files for Cursor, Claude, Codex, and similar tools. "
        "Project source, settings, skills, and cloud chats stay. Opt-in; not part of Full."
    )
    risk = Risk.MODERATE
    requires_admin = False
    default_enabled = False

    def scan(self, progress: ProgressCb | None = None) -> ModuleResult:
        return scan_plans(self, history_plans(), progress)

    def clean(
        self,
        *,
        dry_run: bool = False,
        progress: ProgressCb | None = None,
        only_ids: OnlyIds = None,
    ) -> ModuleResult:
        return clean_plans(
            self,
            history_plans(),
            dry_run=dry_run,
            progress=progress,
            only_ids=only_ids,
        )
