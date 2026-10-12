from __future__ import annotations

import json
import os
from typing import List, Set

REGISTRY_FILE = "app/data/allowed_recipients.json"


def _ensure_file() -> None:
	os.makedirs(os.path.dirname(REGISTRY_FILE), exist_ok=True)
	if not os.path.exists(REGISTRY_FILE):
		with open(REGISTRY_FILE, "w", encoding="utf-8") as f:
			json.dump([], f)


def _load_list() -> List[str]:
	_ensure_file()
	with open(REGISTRY_FILE, "r", encoding="utf-8") as f:
		try:
			data = json.load(f)
			return data if isinstance(data, list) else []
		except Exception:
			return []


def _save_list(items: List[str]) -> None:
	_ensure_file()
	tmp = f"{REGISTRY_FILE}.tmp"
	with open(tmp, "w", encoding="utf-8") as f:
		json.dump(items, f, ensure_ascii=False, indent=2)
	os.replace(tmp, REGISTRY_FILE)


def normalize_email(addr: str) -> str:
	return (addr or "").strip().lower()


def add_recipient(addr: str) -> bool:
	addr_n = normalize_email(addr)
	if not addr_n:
		return False
	items = _load_list()
	if addr_n in {a.lower() for a in items}:
		return False
	items.append(addr_n)
	_save_list(items)
	return True


def is_allowed(addr: str) -> bool:
	addr_n = normalize_email(addr)
	if not addr_n:
		return False
	items = _load_list()
	return addr_n in {a.lower() for a in items}


def all_recipients() -> List[str]:
	return _load_list() 