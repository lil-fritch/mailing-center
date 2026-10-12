from __future__ import annotations
from pathlib import Path
from typing import List, Optional, Tuple, Dict, Any
import shutil
import time

from app.core.logger import logger


class ScreenshotCleaner:
    def __init__(self, base_dir: Path | str = "selenium_data/screenshots"):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _sanitize_email(email: str) -> str:
        return str(email).replace("@", "_at_").replace(".", "_")

    def _list_account_dirs(self, account_email: Optional[str]) -> List[Path]:
        if account_email:
            safe = self._sanitize_email(account_email)
            p = self.base_dir / safe
            return [p] if p.exists() and p.is_dir() else []
        # all account dirs
        return [p for p in self.base_dir.iterdir() if p.is_dir()]

    def list_runs(self, account_email: Optional[str] = None) -> List[Path]:
        runs: List[Path] = []
        for acc_dir in self._list_account_dirs(account_email):
            for run_dir in acc_dir.iterdir():
                if run_dir.is_dir():
                    runs.append(run_dir)
        return runs

    def cleanup(self,
                older_than_days: int = 7,
                account_email: Optional[str] = None,
                dry_run: bool = True,
                limit: Optional[int] = None,
                remove_empty_parents: bool = True
                ) -> Dict[str, Any]:
        now = time.time()
        threshold = now - older_than_days * 86400
        runs = self.list_runs(account_email)
        # sort by mtime ascending (oldest first)
        runs = sorted(runs, key=lambda p: p.stat().st_mtime)
        targets: List[Path] = [p for p in runs if p.stat().st_mtime < threshold]
        if limit is not None:
            targets = targets[:max(0, int(limit))]
        deleted: List[str] = []
        kept: List[str] = [str(p) for p in runs if p not in targets]
        if not dry_run:
            for run_dir in targets:
                try:
                    shutil.rmtree(run_dir, ignore_errors=True)
                    deleted.append(str(run_dir))
                    logger.info(f"Deleted screenshot run dir: {run_dir}")
                    # optionally remove empty parent (account dir)
                    if remove_empty_parents:
                        parent = run_dir.parent
                        if parent.exists() and parent.is_dir() and not any(parent.iterdir()):
                            shutil.rmtree(parent, ignore_errors=True)
                except Exception as e:
                    logger.error(f"Failed to delete {run_dir}: {e}")
        else:
            # dry run: just report what would be deleted
            deleted = [str(p) for p in targets]
        return {
            "deleted": deleted,
            "kept": kept,
            "total_runs": len(runs),
            "to_delete": len(targets),
            "dry_run": dry_run,
        }


screenshot_cleaner = ScreenshotCleaner() 