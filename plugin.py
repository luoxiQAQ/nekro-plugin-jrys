import json
from pathlib import Path
from typing import List

from pydantic import Field

from nekro_agent.api import i18n
from nekro_agent.api.plugin import ConfigBase, ExtraField, NekroPlugin

plugin = NekroPlugin(
    name="今日运势",
    module_name="jrys",
    description="生成今日运势海报，包含运势、幸运星、宜忌与解签文本",
    version="1.0.0",
    author="ominus",
    url="https://github.com/luoxiQAQ/nekro-plugin-jrys",
    i18n_name=i18n.i18n_text(
        zh_CN="今日运势",
        en_US="Daily Fortune",
    ),
    i18n_description=i18n.i18n_text(
        zh_CN="生成今日运势海报，包含运势、幸运星、宜忌与解签文本",
        en_US="Generate a daily fortune poster with luck rating, lucky stars and advice text",
    ),
    allow_sleep=True,
    sleep_brief="用于生成今日运势海报图，在用户询问运势、抽签或求签时激活。",
)

ASSETS_DIR: Path = Path(__file__).resolve().parent / "assets"
BACKGROUND_DIR: Path = ASSETS_DIR / "backgroundFolder"
FONT_DIR: Path = ASSETS_DIR / "font"
DECK_PATH: Path = ASSETS_DIR / "jrys.json"


@plugin.mount_config()
class JrysConfig(ConfigBase):
    """今日运势配置"""

    IMG_WIDTH: int = Field(
        default=1080,
        title="图片宽度",
        description="生成图片的宽度（像素）",
        json_schema_extra=ExtraField(
            i18n_title=i18n.i18n_text(zh_CN="图片宽度", en_US="Image Width"),
            i18n_description=i18n.i18n_text(
                zh_CN="生成图片的宽度（像素）",
                en_US="Width of the generated image in pixels",
            ),
        ).model_dump(),
    )
    IMG_HEIGHT: int = Field(
        default=1920,
        title="图片高度",
        description="生成图片的高度（像素）",
        json_schema_extra=ExtraField(
            i18n_title=i18n.i18n_text(zh_CN="图片高度", en_US="Image Height"),
            i18n_description=i18n.i18n_text(
                zh_CN="生成图片的高度（像素）",
                en_US="Height of the generated image in pixels",
            ),
        ).model_dump(),
    )
    FONT_NAME: str = Field(
        default="千图马克手写体.ttf",
        title="字体名称",
        description="插件 assets/font 目录下的字体文件名",
        json_schema_extra=ExtraField(
            i18n_title=i18n.i18n_text(zh_CN="字体名称", en_US="Font Name"),
            i18n_description=i18n.i18n_text(
                zh_CN="插件 assets/font 目录下的字体文件名",
                en_US="Font file name under the plugin assets/font directory",
            ),
        ).model_dump(),
    )
    AVATAR_CACHE_EXPIRATION: int = Field(
        default=86400,
        title="头像缓存过期时间",
        description="头像缓存的过期时间（秒），默认 86400 秒（一天）",
        json_schema_extra=ExtraField(
            i18n_title=i18n.i18n_text(zh_CN="头像缓存过期时间", en_US="Avatar Cache TTL"),
            i18n_description=i18n.i18n_text(
                zh_CN="头像缓存的过期时间（秒），默认 86400 秒（一天）",
                en_US="Avatar cache expiration time in seconds, default 86400 (one day)",
            ),
        ).model_dump(),
    )
    AVATAR_SIZE: List[int] = Field(
        default=[150, 150],
        title="头像尺寸",
        description="头像绘制的宽高（像素）",
        json_schema_extra=ExtraField(
            sub_item_name="尺寸",
            i18n_title=i18n.i18n_text(zh_CN="头像尺寸", en_US="Avatar Size"),
            i18n_description=i18n.i18n_text(
                zh_CN="头像绘制的宽高（像素）",
                en_US="Avatar width and height in pixels",
            ),
        ).model_dump(),
    )
    AVATAR_POSITION: List[int] = Field(
        default=[60, 1350],
        title="头像位置",
        description="头像左上角坐标（x, y）",
        json_schema_extra=ExtraField(
            sub_item_name="坐标",
            i18n_title=i18n.i18n_text(zh_CN="头像位置", en_US="Avatar Position"),
            i18n_description=i18n.i18n_text(
                zh_CN="头像左上角坐标（x, y）",
                en_US="Top-left coordinate of the avatar (x, y)",
            ),
        ).model_dump(),
    )
    DATE_Y_POSITION: int = Field(
        default=1300,
        title="日期 Y 轴位置",
        description="日期文字的 Y 轴坐标",
        json_schema_extra=ExtraField(
            i18n_title=i18n.i18n_text(zh_CN="日期 Y 轴位置", en_US="Date Y Position"),
            i18n_description=i18n.i18n_text(zh_CN="日期文字的 Y 轴坐标", en_US="Y coordinate of the date text"),
        ).model_dump(),
    )
    SUMMARY_Y_POSITION: int = Field(
        default=1400,
        title="运势总结 Y 轴位置",
        description="运势总结文字的 Y 轴坐标",
        json_schema_extra=ExtraField(
            i18n_title=i18n.i18n_text(zh_CN="运势总结 Y 轴位置", en_US="Summary Y Position"),
            i18n_description=i18n.i18n_text(zh_CN="运势总结文字的 Y 轴坐标", en_US="Y coordinate of the summary text"),
        ).model_dump(),
    )
    LUCKY_STAR_Y_POSITION: int = Field(
        default=1500,
        title="幸运星 Y 轴位置",
        description="幸运星文字的 Y 轴坐标",
        json_schema_extra=ExtraField(
            i18n_title=i18n.i18n_text(zh_CN="幸运星 Y 轴位置", en_US="Lucky Star Y Position"),
            i18n_description=i18n.i18n_text(zh_CN="幸运星文字的 Y 轴坐标", en_US="Y coordinate of the lucky star text"),
        ).model_dump(),
    )
    SIGN_TEXT_Y_POSITION: int = Field(
        default=1600,
        title="签文 Y 轴位置",
        description="简短签文的 Y 轴坐标",
        json_schema_extra=ExtraField(
            i18n_title=i18n.i18n_text(zh_CN="签文 Y 轴位置", en_US="Sign Text Y Position"),
            i18n_description=i18n.i18n_text(zh_CN="简短签文的 Y 轴坐标", en_US="Y coordinate of the sign text"),
        ).model_dump(),
    )
    UNSIGN_TEXT_Y_POSITION: int = Field(
        default=1700,
        title="解签 Y 轴位置",
        description="详细解签文本的 Y 轴坐标",
        json_schema_extra=ExtraField(
            i18n_title=i18n.i18n_text(zh_CN="解签 Y 轴位置", en_US="Unsigned Text Y Position"),
            i18n_description=i18n.i18n_text(
                zh_CN="详细解签文本的 Y 轴坐标",
                en_US="Y coordinate of the detailed advice text",
            ),
        ).model_dump(),
    )
    WARNING_TEXT_Y_POSITION: int = Field(
        default=1850,
        title="注意事项 Y 轴位置",
        description="底部注意事项文字的 Y 轴坐标",
        json_schema_extra=ExtraField(
            i18n_title=i18n.i18n_text(zh_CN="注意事项 Y 轴位置", en_US="Warning Text Y Position"),
            i18n_description=i18n.i18n_text(
                zh_CN="底部注意事项文字的 Y 轴坐标",
                en_US="Y coordinate of the bottom warning text",
            ),
        ).model_dump(),
    )
    KEYWORD_ENABLED: bool = Field(
        default=False,
        title="启用关键词触发",
        description="启用后，群内单独发送 jrys / 今日运势 / 运势 会直接生成海报，且不触发 AI 回复",
        json_schema_extra=ExtraField(
            i18n_title=i18n.i18n_text(zh_CN="启用关键词触发", en_US="Enable Keyword Trigger"),
            i18n_description=i18n.i18n_text(
                zh_CN="启用后，群内单独发送 jrys / 今日运势 / 运势 会直接生成海报，且不触发 AI 回复",
                en_US="When enabled, sending jrys / today's fortune keywords alone triggers the poster and blocks the AI reply",
            ),
        ).model_dump(),
    )
    PRE_CACHE_BACKGROUND: bool = Field(
        default=False,
        title="预缓存背景图",
        description="插件加载时后台预下载 assets/backgroundFolder/*.txt 中的全部图片 URL",
        json_schema_extra=ExtraField(
            i18n_title=i18n.i18n_text(zh_CN="预缓存背景图", en_US="Pre-cache Backgrounds"),
            i18n_description=i18n.i18n_text(
                zh_CN="插件加载时后台预下载 assets/backgroundFolder/*.txt 中的全部图片 URL",
                en_US="Pre-download all background image URLs listed in assets/backgroundFolder/*.txt on plugin load",
            ),
        ).model_dump(),
    )
    PRE_CACHE_CONCURRENCY: int = Field(
        default=3,
        title="预缓存并发数",
        description="预缓存背景图时的并发下载数量，建议 1-10",
        json_schema_extra=ExtraField(
            i18n_title=i18n.i18n_text(zh_CN="预缓存并发数", en_US="Pre-cache Concurrency"),
            i18n_description=i18n.i18n_text(
                zh_CN="预缓存背景图时的并发下载数量，建议 1-10",
                en_US="Concurrent download count when pre-caching backgrounds, 1-10 recommended",
            ),
        ).model_dump(),
    )
    CLEANUP_BACKGROUND_DOWNLOADS: bool = Field(
        default=True,
        title="清理临时背景图",
        description="未启用预缓存时，本次按需下载的背景图在生成完成后删除",
        json_schema_extra=ExtraField(
            i18n_title=i18n.i18n_text(zh_CN="清理临时背景图", en_US="Cleanup Temporary Backgrounds"),
            i18n_description=i18n.i18n_text(
                zh_CN="未启用预缓存时，本次按需下载的背景图在生成完成后删除",
                en_US="When pre-cache is off, on-demand downloaded backgrounds are deleted after generation",
            ),
        ).model_dump(),
    )
    HOLIDAY_RATES_ENABLED: bool = Field(
        default=True,
        title="节假日高爆率",
        description="启用后，在节假日列表中的日期会使用节假日运势权重",
        json_schema_extra=ExtraField(
            i18n_title=i18n.i18n_text(zh_CN="节假日高爆率", en_US="Holiday Boost"),
            i18n_description=i18n.i18n_text(
                zh_CN="启用后，在节假日列表中的日期会使用节假日运势权重",
                en_US="Use holiday fortune weights on dates listed in the holiday list",
            ),
        ).model_dump(),
    )
    FIXED_DAILY_FORTUNE: bool = Field(
        default=True,
        title="每日固定运势",
        description="开启后同一用户当天抽到的运势固定，关闭则每次触发都重新随机",
        json_schema_extra=ExtraField(
            i18n_title=i18n.i18n_text(zh_CN="每日固定运势", en_US="Fixed Daily Fortune"),
            i18n_description=i18n.i18n_text(
                zh_CN="开启后同一用户当天抽到的运势固定，关闭则每次触发都重新随机",
                en_US="When enabled, a user's fortune stays the same for the day; otherwise it is re-rolled every time",
            ),
        ).model_dump(),
    )
    HOLIDAYS: List[str] = Field(
        default=["01-01", "02-14", "05-01", "10-01", "12-25"],
        title="节假日日期列表",
        description="触发高爆率的日期，MM-DD 格式",
        json_schema_extra=ExtraField(
            sub_item_name="日期",
            i18n_title=i18n.i18n_text(zh_CN="节假日日期列表", en_US="Holiday List"),
            i18n_description=i18n.i18n_text(
                zh_CN="触发高爆率的日期，MM-DD 格式",
                en_US="Dates that trigger holiday weights, MM-DD format",
            ),
        ).model_dump(),
    )
    NORMAL_RATE_GOOD: int = Field(
        default=40,
        title="日常·大吉权重",
        description="日常情况下大吉（>70 分）的抽取权重",
        json_schema_extra=ExtraField(
            i18n_title=i18n.i18n_text(zh_CN="日常·大吉权重", en_US="Normal — Great Luck Weight"),
            i18n_description=i18n.i18n_text(
                zh_CN="日常情况下大吉（>70 分）的抽取权重",
                en_US="Draw weight of great luck (>70) on normal days",
            ),
        ).model_dump(),
    )
    NORMAL_RATE_NORMAL: int = Field(
        default=40,
        title="日常·中吉权重",
        description="日常情况下中吉（56~70 分）的抽取权重",
        json_schema_extra=ExtraField(
            i18n_title=i18n.i18n_text(zh_CN="日常·中吉权重", en_US="Normal — Medium Luck Weight"),
            i18n_description=i18n.i18n_text(
                zh_CN="日常情况下中吉（56~70 分）的抽取权重",
                en_US="Draw weight of medium luck (56~70) on normal days",
            ),
        ).model_dump(),
    )
    NORMAL_RATE_BAD: int = Field(
        default=20,
        title="日常·凶运权重",
        description="日常情况下凶运（<56 分）的抽取权重",
        json_schema_extra=ExtraField(
            i18n_title=i18n.i18n_text(zh_CN="日常·凶运权重", en_US="Normal — Bad Luck Weight"),
            i18n_description=i18n.i18n_text(
                zh_CN="日常情况下凶运（<56 分）的抽取权重",
                en_US="Draw weight of bad luck (<56) on normal days",
            ),
        ).model_dump(),
    )
    HOLIDAY_RATE_GOOD: int = Field(
        default=85,
        title="节假日·大吉权重",
        description="节假日大吉（>70 分）的抽取权重",
        json_schema_extra=ExtraField(
            i18n_title=i18n.i18n_text(zh_CN="节假日·大吉权重", en_US="Holiday — Great Luck Weight"),
            i18n_description=i18n.i18n_text(
                zh_CN="节假日大吉（>70 分）的抽取权重",
                en_US="Draw weight of great luck (>70) on holidays",
            ),
        ).model_dump(),
    )
    HOLIDAY_RATE_NORMAL: int = Field(
        default=15,
        title="节假日·中吉权重",
        description="节假日中吉（56~70 分）的抽取权重",
        json_schema_extra=ExtraField(
            i18n_title=i18n.i18n_text(zh_CN="节假日·中吉权重", en_US="Holiday — Medium Luck Weight"),
            i18n_description=i18n.i18n_text(
                zh_CN="节假日中吉（56~70 分）的抽取权重",
                en_US="Draw weight of medium luck (56~70) on holidays",
            ),
        ).model_dump(),
    )
    HOLIDAY_RATE_BAD: int = Field(
        default=0,
        title="节假日·凶运权重",
        description="节假日凶运（<56 分）的抽取权重",
        json_schema_extra=ExtraField(
            i18n_title=i18n.i18n_text(zh_CN="节假日·凶运权重", en_US="Holiday — Bad Luck Weight"),
            i18n_description=i18n.i18n_text(
                zh_CN="节假日凶运（<56 分）的抽取权重",
                en_US="Draw weight of bad luck (<56) on holidays",
            ),
        ).model_dump(),
    )


config = plugin.get_config(JrysConfig)


def load_deck() -> dict:
    """读取运势文案库"""
    with DECK_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)
