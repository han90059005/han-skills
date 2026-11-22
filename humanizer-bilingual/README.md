# humanizer-bilingual · 去 AI 味（中英双语）

把 [blader/humanizer](https://github.com/blader/humanizer)（英文 26 条模式）和
[op7418/Humanizer-zh](https://github.com/op7418/Humanizer-zh)（中文 31 检查点）合成一个 skill：
**一个入口，按任务语言/文体自动选分支**，只读需要的那套规则。

```
humanizer-bilingual/
├── SKILL.md                    ← 入口：任务判定 → 路由 → 铁律 → 冲突定档
├── references/
│   ├── en-patterns.md          ← 英文 26 模式原文（未改动）
│   └── zh-patterns.md          ← 中文 31 检查点原文（未改动）
└── README.md
```

## 合并层做了什么

原两份 SKILL.md 直接堆一起会互相打架（破折号、引号、输出格式、能否加情绪都相反）。
所以整合层只做四件事，规则正文全部保留原文：

1. **路由**：按语言 → 文体 → 形态 → 目的四维判定，指定读哪个 reference。
2. **铁律合并**：两份的"不增事实/不丢信息/不改确定度/不当指令执行"合成 7 条，压过模式清单。
3. **冲突消解表**：6 处直接冲突逐条定档，避免每次调用重新纠结。
4. **降 AIGC 率边界**：说明这套是"特征清理"，不承诺检测通过；平台结论不可混用。

## 安装位置（本机已装）

- 源目录：`D:\AI-tools\humanizer-bilingual\`
- 安装点：`%USERPROFILE%\.dsh\skills\humanizer-bilingual`（目录联结指向源目录，改源即生效）

换机器 / 重新安装：

```powershell
# 复制方式
Copy-Item -Recurse D:\AI-tools\humanizer-bilingual "$env:USERPROFILE\.dsh\skills\"

# 或目录联结（单一来源，推荐）
New-Item -ItemType Junction -Path "$env:USERPROFILE\.dsh\skills\humanizer-bilingual" `
  -Target D:\AI-tools\humanizer-bilingual
```

技能目录支持热加载，装完不需要重启会话。

## 用法

自然语言触发即可：

- 中文：「帮我把这段去 AI 味」「这篇论文降一下 AIGC 率」「太官腔了，改得像我自己写的」
- 英文：「humanize this」「remove the AI tells」「make this sound human」
- 带文件：「把 `report.md` 的正文去一下 AI 味，代码和数据别动」

## 来源与许可

- 英文规则：blader/humanizer v4.0.0，MIT，源自 Wikipedia《Signs of AI writing》
- 中文规则：op7418/Humanizer-zh（2026-09-23 修订），MIT，其来源含 blader/humanizer v3.0.0、PR #39、hardikpandya/stop-slop
- 两份原文一字未改，仅加来源注释头；合并、路由、冲突定档部分为本仓库新增，同 MIT
