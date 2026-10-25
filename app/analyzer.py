from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import tempfile
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.config import (
    CATEGORY_LABELS,
    CATEGORY_QUOTAS,
    CONFIG_DIR,
    DATA_DIR,
    PROJECT_ROOT,
)
from app.models import Candidate, DigestItem


LOGGER = logging.getLogger(__name__)
VALID_CONFIDENCE = {"已确认", "单一来源", "仍在发展"}


class AnalysisError(RuntimeError):
    pass


@dataclass
class AnalysisResult:
    items: list[DigestItem]
    raw_output: str


PROMPT = """你是个人信息差简报的编辑。只依据 stdin 中的候选新闻 JSON，不补充外部事实。

任务：
1. 从候选新闻中选出最多 12 条。分类上限为 AI 5 条、金融 4 条、科技 3 条。
2. 优先选择官方或原始来源、近 36 小时内、有明确影响、跨来源可确认、且容易被普通新闻汇总忽略的信号。
3. 重要性从高到低排列。内容不足时宁可少选，绝不能为了凑数加入低价值新闻。
4. 每条必须使用候选中的 candidate_id 和 category，不得更换网址或虚构来源。
5. 中文输出。what_happened 只写可核实的事实；why_it_matters 和 impact 明确写成分析或推断，不能冒充事实。
6. 不提供投资建议，不声称掌握内幕消息。单一来源必须标为“单一来源”，快速变化的事件标为“仍在发展”。
7. evidence 用一句话说明证据来自哪个来源以及是否有交叉确认。

只返回符合指定 JSON Schema 的 JSON，不要 Markdown、解释或额外字段。
"""

REPAIR_PROMPT = """上一次输出未通过本地校验。请根据错误信息修正，并重新输出完整、合法的 JSON。
不要添加新的事实或候选编号。仍然只返回 JSON。
"""


def analyze(
    candidates: list[Candidate],
    schema_path: Path | None = None,
    timeout_seconds: int = 1800,
) -> AnalysisResult:
    if not candidates:
        raise AnalysisError("No candidates available for analysis")
    codex = shutil.which("codex")
    if not codex:
        raise AnalysisError("Codex CLI not found on PATH")

    schema = (schema_path or CONFIG_DIR / "digest.schema.json").resolve()
    payload = [candidate.analysis_payload() for candidate in candidates]
    raw = _run_codex(codex, schema, PROMPT, payload, timeout_seconds)
    errors = validate_analysis(raw, candidates)
    if errors:
        repair_body = {
            "validation_errors": errors,
            "previous_output": _safe_json(raw),
            "candidates": payload,
        }
        raw = _run_codex(
            codex,
            schema,
            REPAIR_PROMPT,
            repair_body,
            timeout_seconds,
        )
        errors = validate_analysis(raw, candidates)
    if errors:
        raise AnalysisError("Codex output validation failed: " + "; ".join(errors))
    return AnalysisResult(items=_to_items(raw, candidates), raw_output=raw)


def _run_codex(
    codex: str,
    schema: Path,
    prompt: str,
    payload: object,
    timeout_seconds: int,
) -> str:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    temp_dir = DATA_DIR / "tmp"
    temp_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=temp_dir) as temporary:
        output_path = Path(temporary) / "digest.json"
        command = [
            codex,
            "exec",
            "--ephemeral",
            "--skip-git-repo-check",
            "--ignore-rules",
            "--sandbox",
            "read-only",
            "--color",
            "never",
            "--output-schema",
            str(schema),
            "--output-last-message",
            str(output_path),
            "-C",
            str(PROJECT_ROOT),
            prompt,
        ]
        environment = os.environ.copy()
        environment["PYTHONUTF8"] = "1"
        try:
            completed = subprocess.run(
                command,
                input=json.dumps(payload, ensure_ascii=False),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout_seconds,
                env=environment,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise AnalysisError(
                f"Codex timed out after {timeout_seconds} seconds"
            ) from exc

        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout or "").strip()[-3000:]
            raise AnalysisError(
                f"Codex exited with {completed.returncode}: {detail}"
            )
        if not output_path.exists():
            raise AnalysisError("Codex did not create an output file")
        raw = output_path.read_text(encoding="utf-8").strip()
        if not raw:
            raise AnalysisError("Codex returned an empty response")
        LOGGER.info("Codex returned %d characters", len(raw))
        return raw


def validate_analysis(raw: str, candidates: list[Candidate]) -> list[str]:
    errors: list[str] = []
    data = _safe_json(raw)
    if not isinstance(data, dict):
        return ["output must be a JSON object"]
    items = data.get("items")
    if not isinstance(items, list):
        return ["items must be an array"]
    if len(items) > 12:
        errors.append("items exceeds the maximum of 12")

    candidate_map = {candidate.id: candidate for candidate in candidates}
    seen_ids: set[str] = set()
    counts: Counter[str] = Counter()
    required_text = (
        "headline",
        "what_happened",
        "why_it_matters",
        "impact",
        "evidence",
    )
    for index, item in enumerate(items):
        prefix = f"items[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{prefix} must be an object")
            continue
        candidate_id = item.get("candidate_id")
        candidate = candidate_map.get(candidate_id) if isinstance(candidate_id, str) else None
        if candidate is None:
            errors.append(f"{prefix}.candidate_id is not in candidate input")
            continue
        if candidate_id in seen_ids:
            errors.append(f"{prefix}.candidate_id is duplicated")
        seen_ids.add(candidate_id)
        category = item.get("category")
        if category not in CATEGORY_LABELS:
            errors.append(f"{prefix}.category is invalid")
        elif category != candidate.category:
            errors.append(f"{prefix}.category does not match the candidate")
        else:
            counts[category] += 1
        for field in required_text:
            value = item.get(field)
            if not isinstance(value, str) or not value.strip():
                errors.append(f"{prefix}.{field} must be non-empty text")
        if item.get("confidence") not in VALID_CONFIDENCE:
            errors.append(f"{prefix}.confidence is invalid")

    for category, limit in CATEGORY_QUOTAS.items():
        if counts[category] > limit:
            errors.append(f"category {category} exceeds quota {limit}")
    return errors


def _to_items(raw: str, candidates: list[Candidate]) -> list[DigestItem]:
    data = json.loads(raw)
    candidate_map = {candidate.id: candidate for candidate in candidates}
    order = {"ai": 0, "finance": 1, "tech": 2}
    result: list[DigestItem] = []
    for index, raw_item in enumerate(data["items"]):
        candidate = candidate_map[raw_item["candidate_id"]]
        result.append(
            DigestItem(
                id=f"{candidate.id[:12]}-{index:02d}",
                category=raw_item["category"],
                headline=raw_item["headline"].strip(),
                what_happened=raw_item["what_happened"].strip(),
                why_it_matters=raw_item["why_it_matters"].strip(),
                impact=raw_item["impact"].strip(),
                evidence=raw_item["evidence"].strip(),
                confidence=raw_item["confidence"],
                published_at=candidate.published_at.isoformat(),
                sources=candidate.source_refs(),
            )
        )
    return sorted(result, key=lambda item: order[item.category])


def _safe_json(raw: str) -> Any:
    text = raw.strip()
    if text.startswith("```"):
        first_newline = text.find("\n")
        last_fence = text.rfind("```")
        if first_newline >= 0 and last_fence > first_newline:
            text = text[first_newline + 1 : last_fence].strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                pass
    return None

