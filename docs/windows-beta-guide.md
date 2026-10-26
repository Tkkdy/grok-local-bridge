# Windows 内测：先完成无公网测试

对象：Windows x64、PowerShell 5.1、完整 Python 3.13（包含 Tcl/Tk）。这是实验性候选版；真正干净 Windows 首装、winget 自动安装与首次授权窗口仍待外部内测。基础测试不需要 Node、Filesystem、Attention Router 或历史凭据。

## 1. 下载与安装

从维护者提供的准确提交/PR 链接下载。推荐打开该提交的绿色 **Windows offline validation** Actions 运行，在 Artifacts 下载 `candidate-v0.1.1-alpha-<commit>`（GitHub 通常要求登录）。解开外层 artifact ZIP 后，取得源码 ZIP、`RELEASE_MANIFEST.json` 和 `SHA256SUMS.txt`。核对 manifest 的 `source_commit` 是指定提交，并核对源码 ZIP 的 SHA-256：

```powershell
Get-FileHash .\grok-local-bridge-v0.1.1-alpha.zip -Algorithm SHA256
```

也可用维护者提供的 `/archive/<准确提交>.zip`：来自同一提交，但不是上述构建包，文件名、包装层及 SHA-256 不同，不能与构建包的 SHA256SUMS 混比。正式 Release 发布后优先下载 Release 源码包；此文档不代表已经发布。

解压源码，在含 `pyproject.toml` 和 `scripts` 的目录打开 PowerShell，不要覆盖旧安装。首次安装需要联网访问 PyPI/GitHub；即使不启动公网，默认仍下载 cloudflared。

```powershell
$installRoot = Join-Path $env:LOCALAPPDATA 'Grok Local Bridge Alpha Test'
.\scripts\install.ps1 -InstallDir $installRoot -InstallMissingPython
$manage = Join-Path $installRoot 'scripts\connect.ps1'
& $manage -InstallDir $installRoot -CommandArgs @('doctor')
```

缺 Python 时尝试 winget 按用户安装；缺 winget 或安装失败，去 [python.org](https://www.python.org/downloads/windows/) 安装完整 Python 3.13（包含 Tcl/Tk）再重试。缺 Tcl/Tk 会在创建目标前提示；不要关闭 OAuth。doctor 应显示 `owner_ui_available: true`，这只是组件探测，不能代替窗口操作。已有安装时换一个新目录。

若系统阻止脚本，记录错误类别；不要修改全局执行策略、防火墙、代理或 DNS。可先查看下载文件“属性”是否有“解除锁定”，确认来源可信后按组织规则处理。

## 2. 必做：无公网合成测试

```powershell
& $manage -InstallDir $installRoot -CommandArgs @('demo')
& $manage -InstallDir $installRoot -CommandArgs @('verify')
& $manage -InstallDir $installRoot -CommandArgs @('status')
```

预期：verify 为 `PASS_LOCAL_SYNTHETIC`、两个独立后端，status 为 `NOT_STARTED` 且 `manager_alive: false`。demo 只适用于空配置，不要在真实后端安装中重复执行。此步骤不创建 Tunnel、不需要 GrokBot，不代表远程/OAuth 验收。

## 3. 可选：连接 GrokBot

只有愿意公开两项合成工具时才执行：

```powershell
& $manage -InstallDir $installRoot -CommandArgs @('start')
& $manage -InstallDir $installRoot -CommandArgs @('status')
& $manage -InstallDir $installRoot -CommandArgs @('owner')
```

把 status 中本次 `mcp_url` 添加为 GrokBot 远程 MCP，选择 Streamable HTTP / OAuth；用本机窗口配对码完成 Allow，必要时 Continue。配对码只在本机填写。

让 GrokBot 列出连接的**完整目录**，实际调用 `hub_get_hub_state`、`probe_ping`，不用 Shell、不模拟。预期两项工具、`SYNTHETIC`、Ping 为 `pong`、PID 不同。仅发现目录或模型口述成功记为未验证。Quick Tunnel 重建可能换地址，需要更新连接及授权；默认最长 120 分钟，测试后立即停止。

## 4. 停止与卸载

```powershell
& $manage -InstallDir $installRoot -CommandArgs @('stop')
& $manage -InstallDir $installRoot -CommandArgs @('status')
```

确认 `manager_alive: false`，旧远程入口不可用。只停止本安装拥有的进程；停止不等于永久撤销存储授权。

卸载：停止并关闭本安装授权窗口，从 GrokBot 移除临时连接。检查准确的 `$installRoot` 及 `.grok-local-bridge-install` 标记，确认只有本次内测内容，再通过资源管理器删除该独立文件夹，包括 `.runtime`（不保留/重用测试授权数据库），最后删除下载/解压目录。不要删用户允许的文件目录、旧安装、系统 Python 或其他服务；不要求卸载共享 Python。不要对推算路径自动递归清理。

## 5. 脱敏反馈与可选 Filesystem

通过 [GitHub Issues](https://github.com/Tkkdy/grok-local-bridge/issues/new) 提供：

- 版本、`source_commit`、Windows/PowerShell/Python 版本、之前是否有 Python/winget。
- 失败阶段：下载/安装/Tcl-Tk/doctor/demo/verify/授权/目录/调用/停止。
- 预期与实际错误类别、新独立目录能否复现；区分本地测试与真实 Grok。
- 只抄录 `owner_ui_available`、verify 结果、manager_alive 及合成结果；用 `<安装目录>` 替代个人路径，PID 可省略。

**不要上传**原始 status/doctor 全量输出、日志、`.runtime`、数据库、DPAPI、配对码、Token、Cookie、完整回调 URL、个人文件或路径、设备/账号标识；截图先遮挡。安全问题按 [SECURITY](../SECURITY.md) 私下报告。

通过基础流程后，可另看 [可选 Filesystem 配方](filesystem-readonly.md)：Node >=24，用户明确选择测试目录，只读文本与文件名搜索。默认不安装 Node/npm 后端，不默认开放整个磁盘或私人文档。
