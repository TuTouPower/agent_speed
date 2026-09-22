# d002 Kimi CLI 受 Node.js 调用栈物理限制单次 argv 上限为 895KB，采用 850KB (173K Token) 安全切片成功测速且零工具调用

- 来源：`k2.8-preview` 真实测速
- 结论：Kimi CLI（Node.js 实现）在接收命令行 `-p` 参数时，受 Node 默认调用栈物理限制，真实切片代码超过 895KB（约 916KB）时会在启动瞬间触发 `RangeError: Maximum call stack size exceeded` 崩溃（且 Node.js 官方安全策略禁止通过 `NODE_OPTIONS` 修改 `--stack-size`）。通过将输入控制在 850KB（约 173,218 tokens）安全切片以内，Kimi 成功吃满 19.6 万账单输入完成 3 次基准压测，`used_tools` 严格为 `false`，生成 TPS 稳定在 31.8 ~ 34.1 tok/s。
- 证据：`data/results.jsonl` 最新批次（`batch_id: c760d8861f06`），3 次调用全部 success，in_tokens 为 196,077 ~ 196,079，out_tokens 为 3,616 ~ 6,375，`wire.jsonl` 中零工具调用。
- 影响：在调度器与规范中确立 Kimi 的 850KB 安全切片规则与 `cl100k_tokens: 173218` 标注。
- 现状：有效
