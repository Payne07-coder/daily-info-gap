from __future__ import annotations

import argparse
import json
import logging
import os
import shutil
import sys
from collections import Counter
from datetime import datetime
from logging.handlers import RotatingFileHandler

import httpx

from app.analyzer import AnalysisError
from app.config import (
    CATEGORY_LABELS,
    CATEGORY_ORDER,
    DATA_DIR,
    LOG_DIR,
    PROJECT_ROOT,
    SHANGHAI,
    ensure_runtime_dirs,
    load_sources,
)
from app.pipeline import collect, run_pipeline
from app.publisher import PublishError, has_remote, publish_site
from app.render import write_digest
from app.store import Store
from app.system import keep_system_awake
from app.textutil import canonicalize_url, title_key


LOGGER = logging.getLogger("daily_info_gap")


def configure_logging(verbose: bool = False) -> None:
    ensure_runtime_dirs()
    level = logging.DEBUG if verbose else logging.INFO
    formatter = logging.Formatter(
        "%(asctime)s %(levelname)s %(name)s: %(message)s",
        "%Y-%m-%d %H:%M:%S",
    )
    file_handler = RotatingFileHandler(
        LOG_DIR / "pipeline.log",
        maxBytes=2_000_000,
        backupCount=4,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    handlers_to_add = [file_handler]
    file_log_only = (
        os.getenv("DAILY_INFO_GAP_FILE_LOG_ONLY") == "1"
        or sys.stdout is None
        or sys.stderr is None
    )
    if not file_log_only:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        handlers_to_add.append(console_handler)
    if not any(
        getattr(handler, "_daily_info_gap", False)
        for handler in root_logger.handlers
    ):
        for handler in handlers_to_add:
            handler._daily_info_gap = True
            root_logger.addHandler(handler)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="daily-info-gap",
        description="Generate the personal daily information-gap website.",
    )
    parser.add_argument("--verbose", action="store_true")
    subparsers = parser.add_subparsers(dest="command", required=True)

    collect_parser = subparsers.add_parser(
        "collect",
        help="Fetch and inspect sources without calling Codex",
    )
    collect_parser.add_argument(
        "--limit",
        type=int,
        default=5,
        help="Preview items per category",
    )

    run_parser = subparsers.add_parser(
        "run",
        help="Generate the daily digest and optionally publish it",
    )
    run_parser.add_argument(
        "--publish",
        action="store_true",
        help="Commit docs and push to the configured Git remote",
    )

    subparsers.add_parser(
        "doctor",
        help="Check local prerequisites and configuration",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    configure_logging(args.verbose)
    if args.command == "doctor":
        return doctor()
    if args.command == "collect":
        return collect_preview(args.limit)
    if args.command == "run":
        return run_daily(publish=args.publish)
    return 2


def doctor() -> int:
    sources = load_sources()
    counts = Counter(source.category for source in sources)
    codex = shutil.which("codex")
    print(f"项目目录: {PROJECT_ROOT}")
    print(f"启用来源: {len(sources)} ({_category_counts(counts)})")
    print(f"Python: {sys.executable}")
    print(f"Git: {shutil.which('git') or '未找到'}")
    print(f"Codex: {codex or '未找到'}")
    print(f"Git 远端: {'已配置' if has_remote() else '未配置'}")
    try:
        with httpx.Client(timeout=15, follow_redirects=True) as client:
            response = client.head("https://github.com")
        print(f"网络检查: GitHub HTTP {response.status_code}")
    except Exception as exc:
        print(f"网络检查: 失败 ({type(exc).__name__}: {exc})")
    with Store() as store:
        latest_run = store.latest_run()
        print(f"最近运行: {latest_run or '暂无记录'}")
    print("检查完成。")
    return 0


def collect_preview(limit: int) -> int:
    sources = load_sources()
    started = datetime.now(SHANGHAI)
    with Store() as store:
        run_id = store.begin_run(started)
        try:
            collection = collect(sources, now=started)
            store.record_source_status(run_id, collection.source_results, started)
            failures = [
                {"source": result.source.name, "error": result.error}
                for result in collection.source_results
                if result.error
            ]
            print(
                json.dumps(
                    {
                        "sources_ok": len(collection.source_results) - len(failures),
                        "sources_failed": len(failures),
                        "candidates": len(collection.candidates),
                        "failures": failures,
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
            for category in CATEGORY_ORDER:
                print(f"\n【{CATEGORY_LABELS[category]}】")
                category_items = [
                    candidate
                    for candidate in collection.candidates
                    if candidate.category == category
                ][: max(limit, 0)]
                for candidate in category_items:
                    print(f"- {candidate.published_at:%m-%d %H:%M} {candidate.title}")
            store.finish_run(
                run_id,
                "ok",
                datetime.now(SHANGHAI),
                len(collection.candidates),
                "collect preview",
            )
            return 0
        except Exception as exc:
            LOGGER.exception("Collection failed")
            store.finish_run(
                run_id,
                "failed",
                datetime.now(SHANGHAI),
                message=str(exc),
            )
            return 1


def run_daily(publish: bool = False) -> int:
    with keep_system_awake():
        return _run_daily_with_lock(publish)


def _run_daily_with_lock(publish: bool) -> int:
    sources = load_sources()
    started = datetime.now(SHANGHAI)
    with Store() as store:
        run_id = store.begin_run(started)
        try:
            seen_urls, seen_titles = store.seen_markers()
            result = run_pipeline(
                sources,
                seen_urls=seen_urls,
                seen_titles=seen_titles,
                now=started,
            )
            store.record_source_status(run_id, result.collection.source_results, started)

            failures = [
                result.source.name
                for result in result.collection.source_results
                if result.error
            ]
            health = {
                "ok": len(result.collection.source_results) - len(failures),
                "failed": len(failures),
                "failed_sources": failures,
            }
            status = "partial" if failures else "ok"
            digest = write_digest(
                digest_date=result.generated_at.date(),
                generated_at=result.generated_at,
                window_start=result.collection.window_start,
                items=result.analysis.items,
                source_health=health,
                status=status,
            )

            published = False
            if publish:
                published = publish_site()
                store.mark_delivered(
                    result.analysis.items,
                    delivered_date=result.generated_at.date(),
                    created_at=result.generated_at,
                )
                store.cleanup_delivered(result.generated_at.date())

            store.finish_run(
                run_id,
                "ok",
                datetime.now(SHANGHAI),
                len(result.analysis.items),
                f"publish={published}; failed_sources={len(failures)}",
            )
            print(
                f"已生成 {digest['date']} 信息差，共 {len(digest['items'])} 条。"
            )
            print(f"本地网页: {(PROJECT_ROOT / 'docs' / 'index.html')}")
            if publish:
                print("GitHub 发布完成。" if published else "Git 无新内容。")
            else:
                print("本次未发布，也未标记为已读。")
            return 0
        except (AnalysisError, PublishError, RuntimeError, httpx.HTTPError) as exc:
            LOGGER.exception("Daily run failed")
            store.finish_run(
                run_id,
                "failed",
                datetime.now(SHANGHAI),
                message=str(exc),
            )
            return 1
        except Exception as exc:
            LOGGER.exception("Unexpected daily run failure")
            store.finish_run(
                run_id,
                "failed",
                datetime.now(SHANGHAI),
                message=f"{type(exc).__name__}: {exc}",
            )
            return 1


def _category_counts(counts: Counter[str]) -> str:
    return "，".join(
        f"{CATEGORY_LABELS[category]} {counts[category]}"
        for category in CATEGORY_ORDER
    )


if __name__ == "__main__":
    raise SystemExit(main())

