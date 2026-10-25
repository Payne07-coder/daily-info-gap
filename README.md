# 每日信息差

个人使用的每日 AI、金融、科技信息差静态网页。电脑清晨从休眠中醒来，采集公开 RSS，由 Codex 筛选并生成中文卡片，随后发布到 GitHub Pages。

## 当前能力

- 25 个免费 RSS 来源，采集最近 36 小时内容。
- 自动清理跟踪参数、跨来源合并重复新闻。
- AI 5 条、金融 4 条、科技 3 条的分类上限，不为了凑数加入低价值内容。
- Codex 输出经过候选编号、分类配额和字段完整性校验。
- 深色单页看板，手机适配，支持 30 天入口。
- 每天 05:45 定时任务唤醒电脑，07:00 前后网页自动刷新。
- 单个来源失败不阻塞全部内容；失败和运行日志保存在 `logs/pipeline.log`。

## 目录

- `config/sources.json`：新闻来源。
- `config/digest.schema.json`：Codex 输出格式。
- `app/`：采集、去重、Codex 分析、网页数据和发布逻辑。
- `docs/`：GitHub Pages 静态网页。
- `data/state.sqlite`：已推送记录和来源健康，禁止提交。
- `logs/`：本地运行日志，禁止提交。

## 本地安装

所有命令在 PowerShell 中执行：

```powershell
Set-Location D:\Codex\daily-info-gap
$env:PIP_CACHE_DIR = "D:\Codex\daily-info-gap\.cache\pip"
& D:\Codex\Python312\python.exe -m pip install --target .\vendor -r requirements.txt
```

检查环境：

```powershell
& D:\Codex\Python312\python.exe .\launch.py doctor
```

只测试来源采集：

```powershell
& D:\Codex\Python312\python.exe .\launch.py collect
```

用 Codex 生成但当次不发布：

```powershell
& D:\Codex\Python312\python.exe .\launch.py run
```

## GitHub Pages

公开仓库已经创建为 `Payne07-coder/daily-info-gap`，GitHub Pages 已从 `main` 分支的 `/docs` 目录发布，公网地址是：

<https://payne07-coder.github.io/daily-info-gap/>

本机远端使用 HTTPS 和 Git Credential Manager 完成首次登录，不需要每次输入密码。以后每天自动使用的生成和推送命令是：

```powershell
& D:\Codex\Python312\python.exe .\launch.py run --publish
```

发布脚本只提交 `docs/`。数据库、日志和虚拟环境不会进入公开仓库。

项目内另有一枚仅用于这个仓库的备用部署密钥，私钥保存在 `.ssh/`，不会提交。当前 HTTPS 登录已经可用，因此日常流程不依赖 SSH。

## 定时唤醒

以当前 Windows 用户运行：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\setup_tasks.ps1
```

脚本安装两个计划任务：

- `DailyInfoGap`：每天 05:45 唤醒并执行，错过时会在下一次开机补跑。
- `DailyInfoGapHibernate`：07:15 在电脑已空闲至少 10 分钟时重新休眠。

电脑必须接电源、保持不合盖，并在晚间进入休眠。Windows 不能可靠地把已经彻底关机的电脑自动开机。iPhone 热点模式要求手机整夜开启热点；电脑不能自行打开手机热点。

真实唤醒测试：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test_wake.ps1 -AfterMinutes 5
```

该命令会在 10 秒后让电脑休眠。保存工作后运行，等电脑自行唤醒，再检查 `logs/scheduler.log`。

## 已知边界

- 网页仅在浏览器打开时自动刷新，不发送手机系统通知或邮件。
- GitHub Pages 是公开托管的静态页面；网址不宣传，但没有密码保护。
- 信息来自公开来源，不收集内幕消息，不构成投资建议。
- “信息差”依赖来源质量与 Codex 判断，无法保证每条都比所有媒体更早。

