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
REBORN_KEYWORDS = {"逆天改命", "改命"}
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


async def build_poster(user_id: str, salt: str = "", chat_key: str = "") -> Tuple[Path, dict]:
    """生成该用户的今日运势海报，返回 (图片路径, 运势条目)

    chat_key 用于区分群聊，使各群运势与改命次数互相独立；
    salt 非空时用于「逆天改命」——在当天固定种子上追加盐，从而重抽出一个新结果。
    """
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

    # 未显式传盐时，沿用该频道内今天最近一次改命的结果，避免被原始种子顶回去
    effective_salt = salt or resources.active_reborn_salt(chat_key, user_id)

    entry, is_holiday = draw_fortune(
        load_deck(),
        user_id,
        fixed_daily=config.FIXED_DAILY_FORTUNE,
        holiday_enabled=config.HOLIDAY_RATES_ENABLED,
        holidays=list(config.HOLIDAYS),
        normal_rates=_rates("NORMAL"),
        holiday_rates=_rates("HOLIDAY"),
        salt=effective_salt,
        channel=chat_key,
    )
    if is_holiday:
        logger.info(f"命中节假日爆率配置，用户 {user_id} 使用节假日权重")

    out_path = resources.poster_path(user_id, salt=effective_salt, chat_key=chat_key)
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
    resources.remember_background(chat_key, user_id, background_path, should_cleanup)
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
        poster, entry = await build_poster(user_id, chat_key=context.chat_key)
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
    record = resources.last_background(context.chat_key, context.user_id)
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


@plugin.mount_command(
    name="逆天改命",
    description="逆天改命：重新抽取今日运势，每天限指定次数",
    aliases=["改命"],
    usage="逆天改命 [@用户或QQ号]",
    category="娱乐",
)
async def reborn_command(
    context: CommandExecutionContext,
    target: Annotated[str, Arg("目标用户（@提及或 QQ 号），留空为自己", positional=True)] = "",
) -> CommandResponse:
    if not config.REBORN_ENABLED:
        return CmdCtl.failed("逆天改命当前已被关闭，请等待管理员开启～")

    user_id, _nickname = _resolve_target(target, context.user_id)
    chat_key = context.chat_key
    limit = max(0, int(config.REBORN_DAILY_LIMIT))

    remaining = resources.reborn_remaining(chat_key, user_id, limit)
    if remaining <= 0:
        return CmdCtl.failed(
            f"本群今天 {limit} 次改命机会已经用完啦，明天再来吧～\n天命难违，不如安心过好今天。"
        )

    salt = resources.consume_reborn(chat_key, user_id)
    try:
        poster, entry = await build_poster(user_id, salt=salt, chat_key=chat_key)
    except JrysError as e:
        resources.refund_reborn(chat_key, user_id)
        return CmdCtl.failed(str(e))
    except Exception as e:
        resources.refund_reborn(chat_key, user_id)
        logger.exception(f"逆天改命失败: {e}")
        return CmdCtl.failed("改命失败，请稍后再试～")

    left = resources.reborn_remaining(chat_key, user_id, limit)
    return CmdCtl.success(
        [
            CommandOutputSegment(
                type=CommandOutputSegmentType.TEXT,
                text=(
                    f"⚡ 逆天改命成功！新的运势已降临\n"
                    f"{_summary_text(entry)}\n"
                    f"今日剩余改命次数：{left}/{limit}"
                ),
            ),
            CommandOutputSegment(type=CommandOutputSegmentType.IMAGE, file_path=str(poster)),
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
        poster, entry = await build_poster(target_id, chat_key=_ctx.chat_key)
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


@plugin.mount_sandbox_method(
    SandboxMethodType.AGENT,
    name="逆天改命重抽运势",
    description="为用户重新抽取今日运势并发送新海报，每天有次数上限，结果完全随机可能变差",
)
async def jrys_reborn(_ctx: AgentCtx, user_id: str = "", user_name: str = "") -> str:
    """逆天改命：重新抽取今日运势并发送到聊天 (use lang: zh-CN)

    **应用场景: 用户对当天运势不满意、明确要求改命 / 重抽 / 再来一次时使用**
    **注意: 每个用户每天有次数上限，用完即无法再改；新结果完全随机，可能比原来更差**

    Args:
        user_id (str): 目标用户的 QQ 号；留空则取当前消息的发送者
        user_name (str): 目标用户昵称，仅用于日志与文案，可留空

    Returns:
        str: 生成结果与运势摘要
    """
    if not config.REBORN_ENABLED:
        return "逆天改命功能当前已被关闭，无法使用"

    target_id = (user_id or "").strip() or (_ctx.from_platform_userid or "")
    if not target_id:
        return "无法确定目标用户，请提供 QQ 号后重试"

    limit = max(0, int(config.REBORN_DAILY_LIMIT))
    chat_key = _ctx.chat_key
    if resources.reborn_remaining(chat_key, target_id, limit) <= 0:
        return f"该用户在本群今天的 {limit} 次改命机会已用完，无法再次改命"

    salt = resources.consume_reborn(chat_key, target_id)
    try:
        poster, entry = await build_poster(target_id, salt=salt, chat_key=chat_key)
    except JrysError as e:
        resources.refund_reborn(chat_key, target_id)
        return f"改命失败: {e}"
    except Exception as e:
        resources.refund_reborn(chat_key, target_id)
        logger.exception(f"逆天改命失败: {e}")
        return "改命失败，请稍后再试"

    try:
        await message.send_image(_ctx.chat_key, str(poster), _ctx, record=True)
    except Exception as e:
        logger.exception(f"发送改命海报失败: {e}")
        return f"新海报已生成但发送失败: {e}"

    left = resources.reborn_remaining(chat_key, target_id, limit)
    who = user_name or target_id
    return (
        f"已为 {who} 完成逆天改命，新的今日运势已发送。\n"
        f"{entry.get('fortuneSummary', '')} {entry.get('luckyStar', '')}\n"
        f"签文: {entry.get('signText', '')}\n"
        f"今日剩余改命次数: {left}/{limit}\n"
        "请自然地告知用户改命结果，不要重复描述图片细节。"
    )


@plugin.mount_on_user_message()
async def jrys_keyword_handler(_ctx: AgentCtx, message_: ChatMessage) -> Optional[MsgSignal]:
    """群内单独发送关键词时直接出图，并阻止该消息唤醒 AI"""
    if not config.KEYWORD_ENABLED:
        return None

    content = message_.content_text.strip()
    is_reborn = content in REBORN_KEYWORDS
    if content not in KEYWORDS and not is_reborn:
        return None

    user_id = message_.sender_id or message_.platform_userid or ""
    if not user_id:
        return None

    if is_reborn:
        await _handle_keyword_reborn(_ctx, message_, content, user_id)
        return MsgSignal.BLOCK_TRIGGER

    logger.info(f"关键词触发今日运势: {message_.sender_name}({user_id})")
    try:
        poster, _entry = await build_poster(user_id, chat_key=message_.chat_key)
        await message.send_image(message_.chat_key, str(poster), _ctx, record=True)
    except JrysError as e:
        await message.send_text(message_.chat_key, str(e), _ctx, record=False)
    except Exception as e:
        logger.exception(f"关键词触发生成运势失败: {e}")
        await message.send_text(message_.chat_key, "生成运势失败，请稍后再试～", _ctx, record=False)

    return MsgSignal.BLOCK_TRIGGER


async def _handle_keyword_reborn(
    _ctx: AgentCtx, message_: ChatMessage, content: str, user_id: str
) -> None:
    """群内关键词触发逆天改命"""
    if not config.REBORN_ENABLED:
        await message.send_text(message_.chat_key, "逆天改命当前已被关闭～", _ctx, record=False)
        return

    limit = max(0, int(config.REBORN_DAILY_LIMIT))
    chat_key = message_.chat_key
    if resources.reborn_remaining(chat_key, user_id, limit) <= 0:
        await message.send_text(
            message_.chat_key,
            f"本群今天 {limit} 次改命机会已经用完啦，明天再来吧～",
            _ctx,
            record=False,
        )
        return

    logger.info(f"关键词触发逆天改命: {message_.sender_name}({user_id})")
    salt = resources.consume_reborn(chat_key, user_id)
    try:
        poster, entry = await build_poster(user_id, salt=salt, chat_key=chat_key)
    except JrysError as e:
        resources.refund_reborn(chat_key, user_id)
        await message.send_text(message_.chat_key, str(e), _ctx, record=False)
        return
    except Exception as e:
        resources.refund_reborn(chat_key, user_id)
        logger.exception(f"关键词触发逆天改命失败: {e}")
        await message.send_text(message_.chat_key, "改命失败，请稍后再试～", _ctx, record=False)
        return

    left = resources.reborn_remaining(chat_key, user_id, limit)
    await message.send_text(
        message_.chat_key,
        f"⚡ 逆天改命成功！{_summary_text(entry)}（剩余 {left}/{limit}）",
        _ctx,
        record=False,
    )
    try:
        await message.send_image(message_.chat_key, str(poster), _ctx, record=True)
    except Exception as e:
        logger.exception(f"发送改命海报失败: {e}")


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
