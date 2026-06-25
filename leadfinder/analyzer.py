import asyncio
import json
import re

import httpx
from bs4 import BeautifulSoup

from leadfinder.lead_score import calculate_lead_score


class Analyzer:
    async def analyze(self, url: str) -> dict:
        lighthouse_task = self._run_lighthouse(url)
        html_task = self._inspect_html(url)
        lighthouse_result, html_result = await asyncio.gather(lighthouse_task, html_task)

        metrics = {}
        metrics.update(lighthouse_result)
        metrics.update(html_result)

        metrics["lead_score"] = calculate_lead_score(
            performance_score=metrics.get("performance_score", 50),
            seo_score=metrics.get("seo_score", 50),
            best_practices_score=metrics.get("best_practices_score", 50),
            mobile_friendly=metrics.get("mobile_friendly", 0),
        )

        return metrics

    async def _run_lighthouse(self, url: str) -> dict:
        try:
            proc = await asyncio.create_subprocess_exec(
                "lighthouse",
                url,
                "--chrome-flags=--headless",
                "--output=json",
                "--quiet",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            try:
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=60)
            except asyncio.TimeoutError:
                proc.kill()
                raise RuntimeError("Lighthouse timed out")

            if proc.returncode != 0:
                raise RuntimeError(f"Lighthouse failed: {stderr.decode(errors='replace')}")

            data = json.loads(stdout.decode("utf-8"))
            categories = data.get("categories", {})

            return {
                "performance_score": round(categories.get("performance", {}).get("score", 0) * 100),
                "accessibility_score": round(categories.get("accessibility", {}).get("score", 0) * 100),
                "seo_score": round(categories.get("seo", {}).get("score", 0) * 100),
                "best_practices_score": round(categories.get("best-practices", {}).get("score", 0) * 100),
            }
        except FileNotFoundError:
            raise RuntimeError("Lighthouse not found. Install: npm install -g lighthouse")

    async def _inspect_html(self, url: str) -> dict:
        try:
            async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
                response = await client.get(url)
                response.raise_for_status()
        except Exception:
            return {
                "mobile_friendly": 0,
                "has_meta_description": 0,
                "has_open_graph": 0,
                "has_ssl": 0,
                "technologies": [],
            }

        soup = BeautifulSoup(response.text, "html.parser")

        mobile_friendly = 1 if soup.find("meta", attrs={"name": "viewport"}) else 0

        meta_desc = soup.find("meta", attrs={"name": "description"})
        has_meta_description = 1 if meta_desc and meta_desc.get("content", "").strip() else 0

        og_tags = soup.find_all("meta", attrs={"property": re.compile(r"^og:")})
        has_open_graph = 1 if og_tags else 0

        has_ssl = 1 if url.startswith("https") else 0

        technologies = self._detect_technologies(soup)

        return {
            "mobile_friendly": mobile_friendly,
            "has_meta_description": has_meta_description,
            "has_open_graph": has_open_graph,
            "has_ssl": has_ssl,
            "technologies": technologies,
        }

    def _detect_technologies(self, soup: BeautifulSoup) -> list:
        technologies = []

        generator = soup.find("meta", attrs={"name": "generator"})
        if generator:
            content = generator.get("content", "").lower()
            if "wordpress" in content:
                technologies.append("WordPress")
            elif "wix" in content:
                technologies.append("Wix")
            elif "joomla" in content:
                technologies.append("Joomla")
            elif "drupal" in content:
                technologies.append("Drupal")
            elif "shopify" in content:
                technologies.append("Shopify")

        if not technologies:
            scripts = soup.find_all("script", src=True)
            script_srcs = " ".join(s.get("src", "") for s in scripts).lower()
            if "wp-content" in script_srcs or "wp-includes" in script_srcs:
                if "WordPress" not in technologies:
                    technologies.append("WordPress")
            if "wix" in script_srcs:
                if "Wix" not in technologies:
                    technologies.append("Wix")

        return technologies
