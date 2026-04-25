"""
Science Paper Fetcher — PATCH-080b
Batch downloads research papers from arXiv and feeds them into Murphy's
knowledge base for engineering domain advancement.

Supported sources:
  arXiv — mechanical engineering, electrical engineering, fluid dynamics,
           structural, materials science, applied physics, CS/AI

Papers are:
  1. Searched by topic/query
  2. Downloaded (PDF or abstract)
  3. Chunked and stored in Murphy's Knowledge Graph
  4. Used to improve estimates, code gen, and domain reasoning

PATCH-080b | Label: PAPER-FETCH-001
Copyright © 2020-2026 Inoni LLC
"""
from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import arxiv

logger = logging.getLogger(__name__)

PAPERS_DIR = Path(os.environ.get("MURPHY_PAPERS_DIR", "/var/lib/murphy-production/papers"))
PAPERS_DIR.mkdir(parents=True, exist_ok=True)

# Engineering domain → arXiv category + search terms
ENGINEERING_DOMAINS = {
    "mechanical": {
        "categories": ["physics.app-ph", "cond-mat.mtrl-sci"],
        "keywords": ["heat transfer", "fluid dynamics", "HVAC", "thermodynamics",
                     "mechanical design", "fatigue analysis", "finite element"],
    },
    "electrical": {
        "categories": ["eess.SY", "eess.PE"],
        "keywords": ["power systems", "electrical engineering", "circuit design",
                     "motor control", "grounding", "load flow", "protection relay"],
    },
    "structural": {
        "categories": ["physics.app-ph"],
        "keywords": ["structural analysis", "steel design", "concrete", "seismic",
                     "load bearing", "beam column", "foundation design"],
    },
    "materials": {
        "categories": ["cond-mat.mtrl-sci"],
        "keywords": ["material properties", "corrosion", "fatigue", "yield strength",
                     "thermal conductivity", "composite materials"],
    },
    "ai_engineering": {
        "categories": ["cs.AI", "cs.LG"],
        "keywords": ["engineering optimization", "predictive maintenance",
                     "anomaly detection", "digital twin", "autonomous systems"],
    },
}


@dataclass
class FetchedPaper:
    """A fetched research paper."""
    paper_id: str
    title: str
    authors: List[str]
    abstract: str
    categories: List[str]
    published: str
    pdf_url: str
    pdf_path: str = ""
    full_text: str = ""
    ok: bool = True
    error: str = ""


def search_papers(
    query: str,
    domain: str = "general",
    max_results: int = 10,
    sort_by: str = "relevance",
) -> List[FetchedPaper]:
    """
    Search arXiv for engineering papers.
    
    Args:
        query: Natural language search query
        domain: Engineering domain (mechanical/electrical/structural/materials/ai_engineering)
        max_results: Maximum papers to return (default 10, max 50)
        sort_by: "relevance" | "lastUpdatedDate" | "submittedDate"
    
    Returns:
        List of FetchedPaper objects
    """
    sort_map = {
        "relevance": arxiv.SortCriterion.Relevance,
        "lastUpdatedDate": arxiv.SortCriterion.LastUpdatedDate,
        "submittedDate": arxiv.SortCriterion.SubmittedDate,
    }
    sort = sort_map.get(sort_by, arxiv.SortCriterion.Relevance)

    # Enrich query with domain keywords if domain specified
    domain_info = ENGINEERING_DOMAINS.get(domain, {})
    if domain_info.get("keywords"):
        enriched = f"{query} ({domain_info['keywords'][0]})"
    else:
        enriched = query

    try:
        client = arxiv.Client(
            page_size=min(max_results, 50),
            delay_seconds=3.0,  # rate limiting
            num_retries=3,
        )
        search = arxiv.Search(
            query=enriched,
            max_results=min(max_results, 50),
            sort_by=sort,
        )
        papers = []
        for result in client.results(search):
            papers.append(FetchedPaper(
                paper_id=result.entry_id.split("/")[-1],
                title=result.title,
                authors=[str(a) for a in result.authors],
                abstract=result.summary,
                categories=result.categories,
                published=str(result.published.date()),
                pdf_url=result.pdf_url,
            ))
        logger.info("PAPER-FETCH: search(%r) → %d papers", query, len(papers))
        return papers
    except Exception as exc:
        logger.error("PAPER-FETCH: search failed: %s", exc)
        return []


def download_paper(paper: FetchedPaper, download_pdf: bool = False) -> FetchedPaper:
    """
    Download a paper (abstract always, PDF optionally).
    Abstract-only mode is fast and good for most KG ingestion.
    PDF download is slower but gives full methodology/data.
    """
    paper_dir = PAPERS_DIR / paper.paper_id
    paper_dir.mkdir(exist_ok=True)
    meta_path = paper_dir / "meta.json"

    # Always store the abstract
    paper.full_text = f"TITLE: {paper.title}\n\nAUTHORS: {', '.join(paper.authors[:5])}\n\nABSTRACT:\n{paper.abstract}"

    if download_pdf:
        pdf_path = paper_dir / "paper.pdf"
        if pdf_path.exists():
            # Already cached
            paper.pdf_path = str(pdf_path)
            logger.info("PAPER-FETCH: %s — PDF cached", paper.paper_id)
        else:
            try:
                import requests
                resp = requests.get(paper.pdf_url, timeout=30,
                                   headers={"User-Agent": "Murphy/1.0 (research)"})
                resp.raise_for_status()
                pdf_path.write_bytes(resp.content)
                paper.pdf_path = str(pdf_path)
                logger.info("PAPER-FETCH: %s — PDF downloaded (%d bytes)", 
                           paper.paper_id, len(resp.content))
                time.sleep(3)  # be polite to arXiv
            except Exception as exc:
                logger.warning("PAPER-FETCH: %s — PDF download failed: %s", paper.paper_id, exc)
                paper.error = str(exc)
    
    # Save metadata
    meta = {
        "paper_id": paper.paper_id, "title": paper.title,
        "authors": paper.authors, "abstract": paper.abstract,
        "categories": paper.categories, "published": paper.published,
        "pdf_url": paper.pdf_url, "pdf_path": paper.pdf_path,
    }
    meta_path.write_text(json.dumps(meta, indent=2))
    return paper


def batch_fetch_domain(
    domain: str,
    max_papers: int = 20,
    download_pdf: bool = False,
) -> Dict[str, Any]:
    """
    Batch fetch papers for an engineering domain and store in KG.
    
    Returns summary: {domain, fetched, stored_in_kg, papers_list}
    """
    domain_info = ENGINEERING_DOMAINS.get(domain, {})
    keywords = domain_info.get("keywords", [domain])
    
    all_papers = []
    per_keyword = max(1, max_papers // len(keywords[:3]))
    
    for kw in keywords[:3]:
        papers = search_papers(kw, domain=domain, max_results=per_keyword)
        for p in papers:
            p = download_paper(p, download_pdf=download_pdf)
            all_papers.append(p)
        time.sleep(2)  # rate limit

    # Store in knowledge graph
    stored = 0
    for paper in all_papers:
        if store_paper_in_kg(paper):
            stored += 1

    logger.info("PAPER-FETCH: domain=%s fetched=%d stored=%d", domain, len(all_papers), stored)
    return {
        "domain": domain,
        "fetched": len(all_papers),
        "stored_in_kg": stored,
        "papers": [
            {"id": p.paper_id, "title": p.title[:80],
             "published": p.published, "authors": p.authors[:3]}
            for p in all_papers
        ],
    }


def store_paper_in_kg(paper: FetchedPaper) -> bool:
    """Store a paper's abstract and metadata in Murphy's Knowledge Graph."""
    try:
        from src.murphy_memory_palace import MemoryPalace
        palace = MemoryPalace()
        result = palace.index_conversation(
            text=paper.full_text,
            source=f"arxiv:{paper.paper_id}",
            metadata={
                "type": "research_paper",
                "paper_id": paper.paper_id,
                "title": paper.title,
                "authors": ", ".join(paper.authors[:3]),
                "categories": ", ".join(paper.categories),
                "published": paper.published,
                "pdf_url": paper.pdf_url,
            },
        )
        return result.get("status") == "indexed"
    except Exception as exc:
        logger.error("PAPER-FETCH: KG store failed for %s: %s", paper.paper_id, exc)
        return False
