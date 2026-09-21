"""命令、AI 工具与关键词触发入口"""

import asyncio
import os
import re
from pathlib import Path
from typing import Annotated, Optional, Tuple

from nekro_agent.api import message
from nekro_agent.api.plugin import CmdCtl, CommandResponse, SandboxMethodType
from nekro_agent.api.schemas import AgentCtx
from nekro_agent.schemas.chat_message import ChatMessage
from nekro_agent.schemas.signal import MsgSignal
from nekro_agent.services.command.base import CommandPermission
from nekro_agent.services.command.schemas import (
    Arg,
    CommandExecutionContext,
    CommandOutputSegment,
    CommandOutputSegmentType,
)

from .fortune import draw_fortune
from .painter import FortunePainter
from .plugin import config, load_deck, plugin
from .resources import JrysResources

logger = plugin.logger

resources = JrysResources(config)
painter = FortunePainter(config)

KEYWORDS = {"jrys", "今日运势", "运势"}
_AT_MARKUP = re.compile(r"\[@(?:id:)?(?P<uid>\d+)(?:;nickname:(?P<nickname>[^@\]\n]+))?@\]")
_PLAIN_UID = re.compile(r"\d{5,12}")


class JrysError(Exception):
    """可直接展示给用户的失败原因"""


def _resolve_target(raw: str, default_user_id: str) -> Tuple[str, str]:
    """把命令参数解析成 (用户 ID, 昵称)，无法识别时回退到调用者自己"""
    raw = (raw or "").strip()
    if not raw:
        return default_user_id, ""

    match = _AT_MARKUP.search(raw)
    if match:
        return match.group("uid"), (match.group("nickname") or "")

    if _PLAIN_UID.fullmatch(raw):
        return raw, ""

    return default_user_id, ""


def _rates(prefix: str) -> dict:
    return {
        "good": getattr(config, f"{prefix}_RATE_GOOD"),
        "normal": getattr(config, f"{prefix}_RATE_NORMAL"),
        "bad": getattr(config, f"{prefix}_RATE_BAD"),
    }


async def build_poster(user_id: str) -> Tuple[Path, dict]:
    """生成该用户的今日运势海报，返回 (图片路径, 运势条目)"""
    avatar_path, background_result = await asyncio.gather(
        resources.get_avatar_img(user_id),
        resources.get_background_image(),
        return_exceptions=True,
    )

    if isinstance(background_result, Exception):
        logger.error(f"获取背景图片时出错: {background_result}")
        raise JrysError("获取背景图片失败，请稍后再试～")
    if background_result is None:
        logger.error("获取背景图片失败: 返回为空")
        raise JrysError("获取背景图片失败，请稍后再试～")

    background_path, should_cleanup = background_result

    if isinstance(avatar_path, Exception) or avatar_path is None:
        # 头像拿不到不影响出图，只是海报上少个圆头像
        logger.warning(f"获取头像失败，将生成无头像海报: {avatar_path}")
        avatar_path = None

    entry, is_holiday = draw_fortune(
        load_deck(),
        user_id,
        fixed_daily=config.FIXED_DAILY_FORTUNE,
        holiday_enabled=config.HOLIDAY_RATES_ENABLED,
        holidays=list(config.HOLIDAYS),
        normal_rates=_rates("NORMAL"),
        holiday_rates=_rates("HOLIDAY"),
    )
    if is_holiday:
        logger.info(f"命中节假日爆率配置，用户 {user_id} 使用节假日权重")

    out_path = resources.poster_path(user_id)
    poster = await asyncio.to_thread(
        painter.render,
        user_id,
        avatar_path,
        background_path,
        entry,
        out_path,
    )
    if poster is None:
        if should_cleanup and os.path.exists(background_path):
            await asyncio.to_thread(os.remove, background_path)
        raise JrysError("生成图片失败，请稍后再试～")

    # 背景原图转交 jrys_last 管理，不再按临时文件清理
    resources.remember_background(user_id, background_path, should_cleanup)
    return poster, entry


def _summary_text(entry: dict) -> str:
    return f"今日运势：{entry.get('fortuneSummary', '未知')} {entry.get('luckyStar', '')}".strip()


@plugin.mount_command(
    name="jrys",
    description="生成今日运势海报",
    aliases=["今日运势", "运势"],
    usage="jrys [@用户或QQ号]",
    category="娱乐",
)
async def jrys_command(
    context: CommandExecutionContext,
    target: Annotated[str, Arg("目标用户（@提及或 QQ 号），留空为自己", positional=True)] = "",
) -> CommandResponse:
    user_id, _nickname = _resolve_target(target, context.user_id)
    try:
        poster, entry = await build_poster(user_id)
    except JrysError as e:
        return CmdCtl.failed(str(e))
    except Exception as e:
        logger.exception(f"生成今日运势失败: {e}")
        return CmdCtl.failed("生成运势失败，请稍后再试～")

    return CmdCtl.success(
        [
            CommandOutputSegment(type=CommandOutputSegmentType.TEXT, text=_summary_text(entry)),
            CommandOutputSegment(type=CommandOutputSegmentType.IMAGE, file_path=str(poster)),
        ]
    )


@plugin.mount_command(
    name="jrys_last",
    description="重新发送上一次生成运势时使用的原图",
    permission=CommandPermission.PUBLIC,
    usage="jrys_last",
    category="娱乐",
)
async def jrys_last_command(context: CommandExecutionContext) -> CommandResponse:
    record = resources.last_background(context.user_id)
    if not record:
        return CmdCtl.failed("你还没有生成过今日运势哦，先发送 /jrys 生成一张吧！")

    path = record.get("path")
    if not path or not os.path.exists(path):
        return CmdCtl.failed("找不到上一次使用的原图了，可能已被清理，请重新生成～")

    return CmdCtl.success(
        [
            CommandOutputSegment(type=CommandOutputSegmentType.TEXT, text="这是你上次抽到的背景原图～"),
            CommandOutputSegment(type=CommandOutputSegmentType.IMAGE, file_path=path),
        ]
    )


@plugin.mount_sandbox_method(
    SandboxMethodType.AGENT,
    name="生成今日运势海报",
    description="为用户抽取今日运势并生成一张海报图发送到当前聊天，包含运势评级、幸运星与解签文本",
)
async def jrys_poster(_ctx: AgentCtx, user_id: str = "", user_name: str = "") -> str:
    """生成今日运势海报并发送到聊天 (use lang: zh-CN)

    **应用场景: 用户询问运势、抽签、求签、想知道今天运气如何时使用**
    **注意: 同一用户当天运势固定，重复调用只会重新发送同一张运势的海报**

    Args:
        user_id (str): 目标用户的 QQ 号；留空则取当前消息的发送者
        user_name (str): 目标用户昵称，仅用于日志与文案，可留空

    Returns:
        str: 生成结果与运势摘要
    """
    target_id = (user_id or "").strip() or (_ctx.from_platform_userid or "")
    if not target_id:
        return "无法确定目标用户，请提供 QQ 号后重试"

    try:
        poster, entry = await build_poster(target_id)
    except JrysError as e:
        return f"生成失败: {e}"
    except Exception as e:
        logger.exception(f"生成今日运势失败: {e}")
        return "生成运势失败，请稍后再试"

    try:
        await message.send_image(_ctx.chat_key, str(poster), _ctx, record=True)
    except Exception as e:
        logger.exception(f"发送运势海报失败: {e}")
        return f"海报已生成但发送失败: {e}"

    who = user_name or target_id
    return (
        f"已为 {who} 生成并发送今日运势海报。\n"
        f"{entry.get('fortuneSummary', '')} {entry.get('luckyStar', '')}\n"
        f"签文: {entry.get('signText', '')}\n"
        "请结合以上运势内容自然地回应用户，不要重复描述图片细节。"
    )


@plugin.mount_on_user_message()
async def jrys_keyword_handler(_ctx: AgentCtx, message_: ChatMessage) -> Optional[MsgSignal]:
    """群内单独发送关键词时直接出图，并阻止该消息唤醒 AI"""
    if not config.KEYWORD_ENABLED:
        return None

    if message_.content_text.strip() not in KEYWORDS:
        return None

    user_id = message_.sender_id or message_.platform_userid or ""
    if not user_id:
        return None

    logger.info(f"关键词触发今日运势: {message_.sender_name}({user_id})")
    try:
        poster, _entry = await build_poster(user_id)
        await message.send_image(message_.chat_key, str(poster), _ctx, record=True)
    except JrysError as e:
        await message.send_text(message_.chat_key, str(e), _ctx, record=False)
    except Exception as e:
        logger.exception(f"关键词触发生成运势失败: {e}")
        await message.send_text(message_.chat_key, "生成运势失败，请稍后再试～", _ctx, record=False)

    return MsgSignal.BLOCK_TRIGGER


@plugin.mount_init_method()
async def init() -> None:
    # 提前加载并校验文案库，避免首次调用才发现资产缺失
    deck = load_deck()
    logger.info(f"今日运势插件已加载，文案库条目组数: {len(deck)}，背景图 URL: {len(resources.iter_background_urls())}")

    if config.PRE_CACHE_BACKGROUND:
        resources.start_precache()


@plugin.mount_cleanup_method()
async def cleanup() -> None:
    await resources.stop_precache()
    await resources.close()
    logger.info("今日运势插件已卸载")
