from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class SourceRef:
    source_id: str
    source_name: str
    url: str

    def as_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass
class Candidate:
    id: str
    title: str
    summary: str
    url: str
    source_id: str
    source_name: str
    category: str
    published_at: datetime
    source_priority: int
    related_sources: list[SourceRef] = field(default_factory=list)

    def analysis_payload(self) -> dict[str, object]:
        return {
            "candidate_id": self.id,
            "category": self.category,
            "title": self.title,
            "summary": self.summary[:900],
            "published_at": self.published_at.isoformat(),
            "source": {
                "name": self.source_name,
                "url": self.url,
                "priority": self.source_priority,
            },
            "also_reported_by": [
                source.as_dict() for source in self.related_sources[:5]
            ],
        }

    def source_refs(self) -> list[SourceRef]:
        primary = SourceRef(
            source_id=self.source_id,
            source_name=self.source_name,
            url=self.url,
        )
        unique: list[SourceRef] = [primary]
        seen_urls = {self.url}
        for source in self.related_sources:
            if source.url not in seen_urls:
                unique.append(source)
                seen_urls.add(source.url)
        return unique


@dataclass
class DigestItem:
    id: str
    category: str
    headline: str
    what_happened: str
    why_it_matters: str
    impact: str
    evidence: str
    confidence: str
    published_at: str
    sources: list[SourceRef]

    def as_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "category": self.category,
            "headline": self.headline,
            "what_happened": self.what_happened,
            "why_it_matters": self.why_it_matters,
            "impact": self.impact,
            "evidence": self.evidence,
            "confidence": self.confidence,
            "published_at": self.published_at,
            "sources": [source.as_dict() for source in self.sources],
        }


def candidate_id(source_id: str, canonical_url: str, title_key: str) -> str:
    digest = hashlib.sha256(
        f"{source_id}\n{canonical_url}\n{title_key}".encode("utf-8")
    ).hexdigest()
    return digest[:20]

