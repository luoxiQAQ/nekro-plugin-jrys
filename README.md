# 今日运势 (nekro-plugin-jrys)

为群友抽取今日运势并渲染成一张竖版海报，头像、背景与签文一次成图。

这是 AstrBot 插件 [astrbot_plugin_jrys](https://github.com/NINIYOYYO/astrbot_plugin_jrys) 的 nekro-agent 移植版。

## 主要功能

- **今日运势海报**: 从内置文案库按权重抽签，把日期、运势评级、幸运星、签文与解签渲染到随机背景图上，并贴上圆形头像。
- **每日固定运势**: 默认同一用户当天抽到的运势固定，重复请求不会变来变去。
- **节假日高爆率**: 命中节假日列表的日期自动切换到节假日权重（默认大吉概率更高）。
- **背景原图回看**: `/jrys_last` 可以重新取回上一次使用的原图。
- **AI 自动使用**: 对 AI 说“帮我看看今天运势”时，AI 会调用插件生成并发送海报。
- **关键词触发**（默认关闭）: 打开后在群里单独发送 `jrys`、`今日运势`、`运势` 会直接出图且不唤醒 AI。

## 安装

在 nekro-agent WebUI 的插件市场中搜索「今日运势」安装即可，无需额外依赖（使用核心自带的 httpx 与 Pillow）。

## 使用方法

- **命令**: `/jrys`（别名 `/今日运势`、`/运势`）生成自己的运势海报，`/jrys [@某人或QQ号]` 可以替群友抽一张。
- **原图回看**: `/jrys_last` 重新发送上一次生成运势时使用的背景原图。
- **AI 自动使用**: 对 AI 说“帮我看看今天运势”时，AI 会调用插件生成并发送海报。

## 配置说明

- **图片与排版**: 宽度、高度、字体、头像尺寸与位置、各段文字 Y 轴坐标均可调，默认按 1080x1920 排版。
- **爆率权重**: 日常与节假日各有一组大吉 / 中吉 / 凶运权重，按分数段分配。
- **背景图池**: 背景图 URL 放在插件 `assets/backgroundFolder/*.txt` 中，每行一个，可自行增删；开启预缓存后会在插件加载时批量下载。

## 致谢

- 原始 AstrBot 插件：[NINIYOYYO/astrbot_plugin_jrys](https://github.com/NINIYOYYO/astrbot_plugin_jrys)
- nekro-agent 移植：[luoxiQAQ](https://github.com/luoxiQAQ)

## 许可

AGPL-3.0，与上游保持一致，详见 [LICENSE](LICENSE)。
