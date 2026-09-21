"""头像 / 背景图 / 生成图的获取、缓存与状态管理"""

import asyncio
import json
import os
import random
from datetime import datetime
from hashlib import sha256
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse
from uuid import uuid4

import httpx

from .plugin import BACKGROUND_DIR, JrysConfig, plugin

logger = plugin.logger

HTTP_TIMEOUT_SECONDS = 5.0
HTTP_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3"
    )
}


class JrysResources:
    """插件运行期资源：缓存目录、HTTP 客户端、背景图与上次原图状态"""

    def __init__(self, config: JrysConfig) -> None:
        self.config = config
        self.data_dir: Path = plugin.get_plugin_data_dir()
        self.cache_dir: Path = self.data_dir / "cache"
        self.avatar_dir: Path = self.cache_dir / "avatars"
        self.background_cache_dir: Path = self.cache_dir / "background_images"
        self.background_tmp_dir: Path = self.cache_dir / "background_images_tmp"
        self.poster_dir: Path = self.cache_dir / "posters"
        self.state_path: Path = self.data_dir / "state.json"
        self.precache_status_path: Path = self.data_dir / "precache_status.json"

        self._client: Optional[httpx.AsyncClient] = None
        self._state: Dict[str, Any] = {}
        self._state_loaded = False
        self._precache_task: Optional[asyncio.Task[None]] = None

        for directory in (
            self.avatar_dir,
            self.background_cache_dir,
            self.background_tmp_dir,
            self.poster_dir,
        ):
            directory.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------ HTTP

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=HTTP_TIMEOUT_SECONDS,
                limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
                headers=HTTP_HEADERS,
                follow_redirects=True,
            )
        return self._client

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def _download_to_path(self, url: str, dest: Path, label: str = "图片", retries: int = 1) -> bool:
        dest.parent.mkdir(parents=True, exist_ok=True)

        for attempt in range(retries + 1):
            tmp_path = dest.parent / f"{dest.name}.{uuid4().hex}.tmp"
            try:
                async with self.client.stream("GET", url) as response:
                    if response.status_code < 200 or response.status_code >= 300:
                        if 500 <= response.status_code <= 599 and attempt < retries:
                            logger.warning(f"{label}下载失败({attempt + 1}/{retries + 1}): HTTP {response.status_code} | {url}")
                            continue
                        logger.error(f"{label}下载失败: HTTP {response.status_code} | {url}")
                        return False

                    with tmp_path.open("wb") as f:
                        async for chunk in response.aiter_bytes(64 * 1024):
                            f.write(chunk)

                await asyncio.to_thread(os.replace, tmp_path, dest)
                return True
            except asyncio.CancelledError:
                raise
            except httpx.TimeoutException:
                if attempt < retries:
                    logger.warning(f"{label}下载超时({attempt + 1}/{retries + 1}): {url}")
                    await asyncio.sleep(0.2 * (attempt + 1))
                    continue
                logger.error(f"{label}下载超时: {url}")
            except Exception as e:
                message = str(e).strip()[:200]
                if attempt < retries:
                    logger.warning(f"{label}下载失败({attempt + 1}/{retries + 1}): {type(e).__name__}: {message} | {url}")
                    await asyncio.sleep(0.2 * (attempt + 1))
                    continue
                logger.error(f"{label}下载失败: {type(e).__name__}: {message} | {url}")
            finally:
                try:
                    if tmp_path.exists():
                        tmp_path.unlink()
                except OSError:
                    pass

        return False

    # ------------------------------------------------------------- 背景图

    def _cache_path_for_url(self, url: str) -> Path:
        ext = os.path.splitext(urlparse(url).path)[1].lower()
        if not ext or len(ext) > 10:
            ext = ".img"
        return self.background_cache_dir / f"{sha256(url.encode('utf-8')).hexdigest()}{ext}"

    def _tmp_path_for_url(self, url: str) -> Path:
        ext = os.path.splitext(urlparse(url).path)[1].lower()
        if not ext or len(ext) > 10:
            ext = ".img"
        return self.background_tmp_dir / f"{uuid4().hex}{ext}"

    def iter_background_urls(self) -> List[str]:
        urls: List[str] = []
        for path in sorted(BACKGROUND_DIR.glob("*.txt")):
            try:
                for line in path.read_text(encoding="utf-8").splitlines():
                    url = line.strip()
                    if url.startswith("http://") or url.startswith("https://"):
                        urls.append(url)
            except OSError as e:
                logger.warning(f"读取背景图列表失败: {path} | {e}")
        return urls

    async def get_background_image(self) -> Optional[Tuple[str, bool]]:
        """随机取一张背景图，返回 (本地路径, 是否需要在用完后清理)"""
        try:
            urls = await asyncio.to_thread(self.iter_background_urls)
            if not urls:
                logger.warning("没有找到任何背景图片 URL")
                return None

            random.shuffle(urls)
            max_attempts = min(5, len(urls))
            cleanup_downloads = bool(self.config.CLEANUP_BACKGROUND_DOWNLOADS)

            for url in urls[:max_attempts]:
                cache_path = self._cache_path_for_url(url)
                if cache_path.exists():
                    return str(cache_path), False

                image_path = cache_path
                should_cleanup = False
                if (not self.config.PRE_CACHE_BACKGROUND) and cleanup_downloads:
                    image_path = self._tmp_path_for_url(url)
                    should_cleanup = True

                if await self._download_to_path(url, image_path, label="背景图"):
                    return str(image_path), should_cleanup

            logger.warning(f"背景图下载失败: 已尝试 {max_attempts} 个 URL")
            return None
        except Exception as e:
            logger.error(f"获取背景图片时出错: {e}")
            return None

    # -------------------------------------------------------------- 头像

    async def get_avatar_img(self, user_id: str) -> Optional[str]:
        try:
            avatar_path = self.avatar_dir / f"{user_id}.jpg"
            if avatar_path.exists():
                try:
                    file_age = datetime.now().timestamp() - avatar_path.stat().st_mtime
                    if file_age < self.config.AVATAR_CACHE_EXPIRATION:
                        return str(avatar_path)
                except OSError:
                    pass

            url = f"http://q.qlogo.cn/g?b=qq&nk={user_id}&s=640"
            if await self._download_to_path(url, avatar_path, label="头像"):
                return str(avatar_path)
            return None
        except Exception as e:
            logger.error(f"获取用户头像失败: {e}")
            return None

    # ---------------------------------------------------------- 生成图路径

    def poster_path(self, user_id: str) -> Path:
        return self.poster_dir / f"jrys_{user_id}.jpg"

    # -------------------------------------------------------------- 状态

    def load_state(self) -> Dict[str, Any]:
        if self._state_loaded:
            return self._state
        try:
            if self.state_path.exists():
                self._state = json.loads(self.state_path.read_text(encoding="utf-8"))
            else:
                self._state = {}
        except (OSError, json.JSONDecodeError) as e:
            logger.warning(f"读取运势状态文件失败，将重新初始化: {e}")
            self._state = {}
        self._state_loaded = True
        return self._state

    def save_state(self) -> None:
        try:
            self.state_path.write_text(
                json.dumps(self._state, ensure_ascii=False, indent=4),
                encoding="utf-8",
            )
        except OSError as e:
            logger.error(f"保存运势状态失败: {e}")

    def last_background(self, user_id: str) -> Optional[Dict[str, Any]]:
        return self.load_state().get("last_images", {}).get(user_id)

    def remember_background(self, user_id: str, background_path: str, should_cleanup: bool) -> None:
        state = self.load_state()
        last_images = state.setdefault("last_images", {})

        previous = last_images.get(user_id)
        if previous and previous.get("should_cleanup"):
            previous_path = previous.get("path")
            # 上次的临时图与本张不同才清理，避免删掉正在复用的文件
            if previous_path and previous_path != background_path and os.path.exists(previous_path):
                try:
                    os.remove(previous_path)
                except OSError:
                    pass

        last_images[user_id] = {"path": background_path, "should_cleanup": should_cleanup}
        self.save_state()

    # ------------------------------------------------------------ 预缓存

    def start_precache(self) -> None:
        if self._precache_task and not self._precache_task.done():
            return
        self._precache_task = asyncio.create_task(self._precache_backgrounds())

    async def stop_precache(self) -> None:
        if self._precache_task and not self._precache_task.done():
            self._precache_task.cancel()
            try:
                await self._precache_task
            except asyncio.CancelledError:
                pass
            except Exception as e:
                logger.warning(f"预缓存任务清理失败: {e}")
        self._precache_task = None

    def _write_precache_status(self, payload: Dict[str, Any]) -> None:
        try:
            self.precache_status_path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=4),
                encoding="utf-8",
            )
        except OSError as e:
            logger.warning(f"写入预缓存状态失败: {e}")

    async def _precache_backgrounds(self) -> None:
        urls = sorted(set(await asyncio.to_thread(self.iter_background_urls)))
        if not urls:
            logger.warning("预缓存背景图：未找到任何图片 URL")
            return

        concurrency = max(1, min(int(self.config.PRE_CACHE_CONCURRENCY), 10))
        pending = [(url, self._cache_path_for_url(url)) for url in urls]
        todo = [(url, dest) for url, dest in pending if not dest.exists()]
        already_cached = len(pending) - len(todo)

        logger.info(
            f"预缓存背景图开始: total={len(pending)}, cached={already_cached}, "
            f"download={len(todo)}, concurrency={concurrency}"
        )
        self._write_precache_status(
            {
                "status": "running",
                "total": len(pending),
                "cached": already_cached,
                "download": len(todo),
                "started_at": datetime.now().isoformat(),
            }
        )

        semaphore = asyncio.Semaphore(concurrency)

        async def download(url: str, dest: Path) -> bool:
            if dest.exists():
                return True
            async with semaphore:
                if dest.exists():
                    return True
                return await self._download_to_path(url, dest, label="背景图")

        downloaded = 0
        failed = 0
        cancelled = False
        try:
            results = await asyncio.gather(
                *(download(url, dest) for url, dest in todo),
                return_exceptions=True,
            )
            for result in results:
                if result is True:
                    downloaded += 1
                else:
                    failed += 1
        except asyncio.CancelledError:
            cancelled = True
            raise
        finally:
            self._write_precache_status(
                {
                    "status": "cancelled" if cancelled else "done",
                    "total": len(pending),
                    "cached": already_cached,
                    "download": len(todo),
                    "downloaded": downloaded,
                    "failed": failed,
                    "ended_at": datetime.now().isoformat(),
                }
            )

        logger.info(
            f"预缓存背景图完成: total={len(pending)}, cached={already_cached}, "
            f"downloaded={downloaded}, failed={failed}"
        )
