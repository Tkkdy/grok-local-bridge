# Troubleshooting / 故障诊断

先分清：本地后端 → 聚合/认证 → 公网传输 → 客户端。端口可达、Inspector 成功、模型口述与真实 Grok 调用不是同一验收。

| 现象 | 检查与动作 |
|---|---|
| 安装或模块找不到状态 | 用安装目录的 scripts/connect.ps1；直接模块调用需要同一安装 venv，或显式 --home。不要引用旧 Skill 缓存或旧运行目录 |
| 401 | 无授权的 401 是保护正常；检查 OAuth metadata、当前 origin、grant 到期/撤销。不要输出 Token |
| Allow 后没有换取授权 | 完成本地结果页的 Continue；核对 callback 是否精确允许、授权页是否已过期。不要反复点一次性 Allow |
| invalid_client | Quick URL/issuer 变更或客户端缓存旧注册；用本次 URL 重新连接/授权 |
| 缺工具/目录报错 | 等 APPLIED、核对 config 工具白名单和后端是否在线，再刷新完整命名空间。若一个后端离线，目录故意报错，已知健康工具仍可直调 |
| 新工具保存但未可见 | 保存不等于运行时生效，查看 generation、backend_count、tool_count 与错误；客户端目录也需要刷新 |
| Removed tool 仍在客户端列表 | 缓存不等于授权；APPLIED 后新调用应被拒绝，已有调用可能完成 |
| 429 / Tool rate limit | 等待分钟窗口；全局 ingress 和单工具窗口独立，不要以反复重启规避 |
| 502/530、TLS/网络失败 | 读 status 分清本地 Gateway、Tunnel 和公网路径；保存脱敏错误类别。不擅自关闭 TUN、改防火墙或 DNS |
| GET /mcp 405 | 支持的是 stateless JSON POST；不要把可选 SSE GET 失败当作所有 MCP 失败 |
| stdio 状态丢失 | 每请求新进程是当前设计；有状态 MCP 可改用本地常驻 HTTP，再单独验收 |
| WorkBuddy 提示找不到 md | 既有普通 UI 导入仍失败；本地解包可发现入口不代表云端通过。若 UI 不暴露底层错误，记录包哈希/阶段/脱敏错误，交官方支持；不要猜目录层级、绕过检查或调用隐藏接口 |

`status` 是本地状态读取；`diagnose` 会访问本地和当前公网 HTTP 健康路径。均不能证明 Grok 已实际调用。不要提供完整 OAuth 回调 URL、账户截图、Cookie、Token 或未经清理日志。
