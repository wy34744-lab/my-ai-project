from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List
from urllib.parse import urljoin
import zipfile

import requests
from bs4 import BeautifulSoup
from PIL import Image, ImageEnhance, ImageFilter, ImageDraw


OUTPUT_ROOT = Path("outputs")
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0.0.0 Safari/537.36"
)


@dataclass
class RemixResult:
    job_id: str
    output_dir: Path
    zip_file: Path
    note_file: Path
    images: List[Path]


@dataclass
class NoteMaterial:
    source_url: str
    title: str
    body: str
    tags: List[str]
    image_urls: List[str]


def _job_id() -> str:
    return f"{datetime.now().strftime('%Y%m%d')}_{uuid.uuid4().hex[:8]}"


def fetch_note_material(note_url: str) -> NoteMaterial:
    headers = {"User-Agent": USER_AGENT}
    response = requests.get(note_url, headers=headers, timeout=20)
    response.raise_for_status()
    html = response.text
    soup = BeautifulSoup(html, "html.parser")

    title = _extract_title(soup)
    body = _extract_body(soup)
    tags = _extract_tags(title, body)
    image_urls = _extract_image_urls(soup, note_url)

    return NoteMaterial(
        source_url=note_url,
        title=title,
        body=body,
        tags=tags,
        image_urls=image_urls,
    )


def _extract_title(soup: BeautifulSoup) -> str:
    title = ""
    if soup.title and soup.title.text:
        title = soup.title.text.strip()
    og_title = soup.find("meta", attrs={"property": "og:title"})
    if og_title and og_title.get("content"):
        title = og_title["content"].strip()
    return title or "今日美食分享"


def _extract_body(soup: BeautifulSoup) -> str:
    selectors = [
        "meta[name='description']",
        "meta[property='og:description']",
        "script[type='application/ld+json']",
    ]
    for selector in selectors:
        node = soup.select_one(selector)
        if not node:
            continue
        if selector.startswith("script"):
            text = node.get_text(strip=True)
            if not text:
                continue
            try:
                data = json.loads(text)
                if isinstance(data, dict):
                    for key in ["description", "articleBody", "text"]:
                        if data.get(key):
                            return str(data[key]).strip()
            except json.JSONDecodeError:
                continue
        else:
            content = node.get("content", "").strip()
            if content:
                return content

    raw_text = soup.get_text("\n", strip=True)
    clean_text = re.sub(r"\n+", "\n", raw_text)
    return clean_text[:800]


def _extract_tags(title: str, body: str) -> List[str]:
    text = f"{title} {body}"
    candidates = re.findall(r"#([\w\u4e00-\u9fff]{2,20})", text)
    if candidates:
        return list(dict.fromkeys(candidates))[:8]
    default_tags = ["美食", "家常菜", "今日份晚餐", "下饭菜", "厨房日记"]
    return default_tags


def _extract_image_urls(soup: BeautifulSoup, base_url: str) -> List[str]:
    urls: List[str] = []
    og_image = soup.find("meta", attrs={"property": "og:image"})
    if og_image and og_image.get("content"):
        urls.append(urljoin(base_url, og_image["content"]))

    for img in soup.find_all("img"):
        for key in ["src", "data-src", "data-origin-src"]:
            src = img.get(key)
            if src and src.startswith("http"):
                urls.append(src)
                break

    dedup = []
    seen = set()
    for u in urls:
        if u in seen:
            continue
        seen.add(u)
        dedup.append(u)
    return dedup[:12]


def rewrite_note(material: NoteMaterial, theme: str, extra_edit_prompt: str | None = None) -> str:
    intro = f"今天做一期【{theme}】灵感改编，复刻思路更简单，在家也能轻松出片！"
    body = (
        f"原笔记核心信息：{material.body[:180]}...\n\n"
        f"我把内容重组为更适合{theme}的做法：\n"
        "1. 食材准备按‘主料-辅料-调味’拆分，避免漏步骤；\n"
        "2. 烹饪过程强调‘火候+时长’，新手更容易成功；\n"
        "3. 出锅前补一个摆盘动作，照片更有食欲。\n"
    )
    if extra_edit_prompt:
        body += f"\n额外风格要求：{extra_edit_prompt}\n"

    tags = material.tags[:5]
    if theme not in tags:
        tags.insert(0, theme)
    tags_line = " ".join(f"#{t}" for t in tags)

    return (
        f"# {theme}｜改编版美食笔记\n\n"
        f"来源链接：{material.source_url}\n\n"
        f"{intro}\n\n"
        f"{body}\n"
        f"{tags_line}\n"
    )


def _crop_to_ratio(image: Image.Image, ratio_w: int = 4, ratio_h: int = 5) -> Image.Image:
    target_ratio = ratio_w / ratio_h
    src_w, src_h = image.size
    src_ratio = src_w / src_h

    if src_ratio > target_ratio:
        new_w = int(src_h * target_ratio)
        left = (src_w - new_w) // 2
        box = (left, 0, left + new_w, src_h)
    else:
        new_h = int(src_w / target_ratio)
        top = (src_h - new_h) // 2
        box = (0, top, src_w, top + new_h)
    return image.crop(box)


def _apply_food_enhancement(image: Image.Image) -> Image.Image:
    image = ImageEnhance.Color(image).enhance(1.18)
    image = ImageEnhance.Contrast(image).enhance(1.08)
    image = ImageEnhance.Sharpness(image).enhance(1.12)
    image = image.filter(ImageFilter.DETAIL)
    return image


def _add_watermark(image: Image.Image, text: str = "二创") -> Image.Image:
    draw = ImageDraw.Draw(image)
    x, y = image.size
    anchor = (x - 90, y - 45)
    draw.rectangle((anchor[0] - 8, anchor[1] - 6, anchor[0] + 60, anchor[1] + 22), fill=(0, 0, 0, 90))
    draw.text(anchor, text, fill=(255, 255, 255))
    return image


def process_images(image_urls: List[str], output_image_dir: Path) -> List[Path]:
    headers = {"User-Agent": USER_AGENT}
    output_image_dir.mkdir(parents=True, exist_ok=True)

    generated: List[Path] = []
    for idx, url in enumerate(image_urls[:6], start=1):
        try:
            raw = requests.get(url, headers=headers, timeout=20)
            raw.raise_for_status()
            tmp_path = output_image_dir / f"origin_{idx}.jpg"
            tmp_path.write_bytes(raw.content)

            with Image.open(tmp_path).convert("RGB") as img:
                remixed = _crop_to_ratio(img, 4, 5)
                remixed = _apply_food_enhancement(remixed)
                remixed = _add_watermark(remixed)
                final_path = output_image_dir / f"remix_{idx}.jpg"
                remixed.save(final_path, quality=92)
                generated.append(final_path)
            tmp_path.unlink(missing_ok=True)
        except Exception:
            continue

    return generated


def bundle_output(output_dir: Path) -> Path:
    zip_file = output_dir / "result.zip"
    with zipfile.ZipFile(zip_file, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for item in output_dir.rglob("*"):
            if item == zip_file:
                continue
            if item.is_file():
                zf.write(item, item.relative_to(output_dir))
    return zip_file


def run_workflow(note_url: str, theme: str, extra_edit_prompt: str | None = None) -> RemixResult:
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    job = _job_id()
    output_dir = OUTPUT_ROOT / job
    output_dir.mkdir(parents=True, exist_ok=True)

    material = fetch_note_material(note_url)
    note_text = rewrite_note(material, theme=theme, extra_edit_prompt=extra_edit_prompt)

    note_file = output_dir / "remix_note.md"
    note_file.write_text(note_text, encoding="utf-8")

    image_dir = output_dir / "images"
    generated_images = process_images(material.image_urls, image_dir)

    zip_file = bundle_output(output_dir)

    return RemixResult(
        job_id=job,
        output_dir=output_dir.resolve(),
        zip_file=zip_file.resolve(),
        note_file=note_file.resolve(),
        images=[x.resolve() for x in generated_images],
    )
