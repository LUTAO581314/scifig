"""机制图图标库集成（Bioicons，开源科研图标，~2830 个）。

推荐用法：把 Bioicons 仓库 clone 到本地，通过环境变量指定目录：
    SCIFIG_BIOICONS_DIR=<bioicons 仓库根目录>
然后用独家图标（细胞/分子/蛋白/DNA/病毒/仪器等）搜索并获取。

若未配置本地目录，回退到远程 raw.githubusercontent.com 逐个下载
（需能访问 GitHub，且依赖 icons.json 索引路径——作者名可能含空格差异，
建议使用本地目录以获得最高的路径可靠性）。

类目（38 个）：Cell_membrane, Molecular_Biology, Chemistry, Nucleic_acids,
    Viruses, Animals, Imaging, Lab_apparatus, Human_physiology,
    Intracellular_components, Machine_Learning, Microbiological … 等。

IR 用法，节点加 icon 字段：
    {"id":"n1","label":"细胞","icon":"cell_membrane"}          # 关键词
    {"id":"n2","icon":{"name":"DNA","category":"Nucleic_acids"}} # 精确
    {"id":"n3","icon":{"path":"cc-0/Nucleic_acids/Kumar/DNA.svg"}} # 直接指定相对路径
"""

from __future__ import annotations

import json
import os
import re
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional

_INDEX_BIO_URL = "https://raw.githubusercontent.com/duerrsimon/bioicons/master/static/icons/icons.json"
_SVG_BASE = "https://raw.githubusercontent.com/duerrsimon/bioicons/master/static/icons"

_ROOT = Path(__file__).resolve().parents[3]  # 项目根
_CACHE = Path(os.environ.get("SCIFIG_ICON_CACHE", str(_ROOT / ".iconlib_cache")))


def _bio_dir() -> str:
    return os.environ.get("SCIFIG_BIOICONS_DIR", "")


# 本地/远程索引：list[node= Dict], node字段包含 name/category/rel(相对路径)/license
_local_index: Optional[List[Dict[str, Any]]] = None
_remote_index: Optional[List[Dict[str, Any]]] = None


def _ensure_local_index() -> Optional[List[Dict[str, Any]]]:
    """遍历本地 Bioicons 目录建立 name→rel 路径索引。未配置返回 None。"""
    global _local_index
    if _local_index is not None:
        return _local_index
    bio = _bio_dir()
    if not bio:
        _local_index = []  # 标记已尝试
        return None
    base = Path(bio)
    icons_dir = base / "static" / "icons"
    if not icons_dir.exists():
        raise RuntimeError(f"SCIFIG_BIOICONS_DIR 下找不到 static/icons: {bio}")
    items: List[Dict[str, Any]] = []
    for f in icons_dir.rglob("*.svg"):
        rel = f.relative_to(icons_dir).as_posix()
        name = f.stem
        segs = rel.split("/")
        category = segs[1] if len(segs) >= 3 else ""
        license_ = segs[0] if segs else ""
        items.append({"name": name, "category": category, "license": license_,
                      "rel": rel, "path": str(f)})
    _local_index = items
    return items


def _ensure_remote_index() -> List[Dict[str, Any]]:
    """拉取远程 icons.json 建索引（作者名可能与实际路径有空格差异）。"""
    global _remote_index
    if _remote_index is not None:
        return _remote_index
    _CACHE.mkdir(parents=True, exist_ok=True)
    idx_path = _CACHE / "icons.json"
    if not idx_path.exists():
        _download(_INDEX_BIO_URL, idx_path)
    raw = json.loads(idx_path.read_text(encoding="utf-8"))
    _remote_index = [{
        "name": str(it.get("name", "")),
        "category": str(it.get("category", "")),
        "license": str(it.get("license", "")),
        # 远程 rel 用索引的 author；可能含空格=>需 URL 编码
        "rel": f'{it.get("license")}/{it.get("category")}/{it.get("author")}/{it.get("name")}.svg',
    } for it in raw]
    return _remote_index


def _download(url: str, dest: Path) -> None:
    req = urllib.request.Request(url, headers={"User-Agent": "scifig/0.1"})
    with urllib.request.urlopen(req, timeout=30) as r:
        dest.write_bytes(r.read())


def _index() -> List[Dict[str, Any]]:
    loc = _ensure_local_index()
    if loc is not None and loc:
        return loc
    return _ensure_remote_index()


def _match_score(it: Dict[str, Any], kws: set) -> int:
    """返回匹配得分：全部关键词命中=高分；否则部分命中低分。"""
    name = it["name"].lower()
    hits = sum(1 for k in kws if k in name)
    if not kws:
        return 0
    return hits


def search_icons(keyword: str, category: Optional[str] = None,
                 limit: int = 8) -> List[Dict[str, str]]:
    """按关键词（和可选分类）搜索图标，精确名优先。返回 [{name, category, rel, license}]。"""
    kws = set(re.sub(r"[^a-z0-9]+", " ", keyword.lower()).strip().split())
    key_norm = re.sub(r"[^a-z0-9]+", "", keyword.lower())
    exact: List[tuple[int, Dict[str, str]]] = []
    scored: List[tuple[int, Dict[str, str]]] = []
    for it in _index():
        cat = it.get("category", "")
        if category and cat != category:
            continue
        name_norm = re.sub(r"[^a-z0-9]+", "", it["name"].lower())
        rec = {
            "name": it["name"], "category": cat,
            "license": it.get("license", ""), "rel": it["rel"],
        }
        if key_norm and name_norm == key_norm:
            exact.append((0, rec))
            continue
        score = _match_score(it, kws)
        if score > 0:
            scored.append((score, rec))
    scored.sort(key=lambda x: (-x[0], x[1]["name"]))
    exact.sort(key=lambda x: x[1]["name"])
    combined = [s for _, s in exact] + [s for _, s in scored]
    return combined[:limit]


def categories() -> List[str]:
    """返回图标分类列表（本地遍历时从路径提取；远程用 categories.json）。"""
    loc = _ensure_local_index()
    if loc is not None and loc:
        return sorted({it["category"] for it in loc if it.get("category")})
    # 远程分类
    _CACHE.mkdir(parents=True, exist_ok=True)
    cp = _CACHE / "categories.json"
    if not cp.exists():
        _download(
            "https://raw.githubusercontent.com/duerrsimon/bioicons/master/static/icons/categories.json",
            cp)
    return json.loads(cp.read_text(encoding="utf-8"))


def resolve_icon(spec: Any) -> Optional[Dict[str, str]]:
    """把 IR 节点的 icon 字段解析为一个图标条目 {name, rel}。找不到返回 None。"""
    if spec is None:
        return None
    if isinstance(spec, dict):
        if spec.get("path"):
            return {"name": Path(spec["path"]).stem,
                    "rel": spec["path"], "explicit": "1"}
        name = spec.get("name")
        cat = spec.get("category")
        if name:
            hits = search_icons(str(name), category=cat, limit=1)
            return hits[0] if hits else None
        return None
    if isinstance(spec, str):
        hits = search_icons(spec, limit=1)
        return hits[0] if hits else None
    return None


def fetch_icon_svg(entry: Dict[str, str], as_text: bool = False) -> Any:
    """返回图标 SVG 内容（本地优先；否则远程下载到缓存）。as_text=True 返回字符串。"""
    loc = _ensure_local_index()
    if loc is not None and loc:
        # 本地：按 rel 匹配
        target = Path(_bio_dir()) / "static" / "icons" / entry["rel"]
        if target.exists():
            txt = target.read_text(encoding="utf-8", errors="replace")
            return txt if as_text else str(target)
        # 尝试按名字找（rel 可能不准）
        cand = [it for it in loc if it["name"].lower() == entry["name"].lower()]
        if cand:
            p = cand[0]["path"]
            txt = Path(p).read_text(encoding="utf-8", errors="replace")
            return txt if as_text else p
        raise FileNotFoundError(f"本地图标未找到: {entry.get('name')}")

    # 远程：下载到缓存
    from urllib.parse import quote, urlparse
    flat = re.sub(r"[^A-Za-z0-9_.-]", "__", entry["rel"])
    dest = _CACHE / f"{flat}"
    if not dest.exists():
        # rel 里作者可能含空格，逐段编码
        segs = entry["rel"].split("/")
        encoded = "/".join(quote(s, safe="") for s in segs)
        _download(f"{_SVG_BASE}/{encoded}", dest)
    txt = dest.read_text(encoding="utf-8", errors="replace")
    return txt if as_text else str(dest)


def svg_body(icon_svg: str) -> str:
    """去掉 SVG 外壳，返回可内联的 <g>/内容。"""
    body = re.sub(r"<\?xml.*?\?>", "", icon_svg)
    body = re.sub(r"<!--.*?-->", "", body, flags=re.S)
    body = re.sub(r"<svg[^>]*>", "", body, count=1)
    body = re.sub(r"</svg>", "", body)
    return body.strip()
