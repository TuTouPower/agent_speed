# d004 粗粒度流上客户端滚动峰值 TPS 不可测：opencode/mimo 协议长输出只分 1~2 个巨块，结果只能是 None 或约等于总 token 数

- 来源：日常（2026-09-23 MiniMax/mimo 三档 36 次实测 + 估算器已 revert）
- 结论：字符分摊 + 1s 滑窗的峰值估算只在细碎增量流（如 mcode 595 个 delta，见 d003）上成立；opencode/mimo 协议把长输出攒成 1~2 个巨块一次刷出，同一格 3 次可量出 None、1639、8334 这种彩票组合，属网络 flush 假象而非解码速度，相关代码已整体 revert。
- 证据：200k 档 mimo-v2.6-pro 三次 peak 为 None/8334/None（e2e 54/53/56 正常），10k 档 mimo-flash 出现 4031/5674、MiniMax 三次全 None；估算器对同 tick（span 0）返回 None、tick 相差 0.1s 则约等于总输出 token。
- 影响：榜单继续只用端到端与生成 TPS；`data/results.jsonl` 历史行里残留实验性 `peak_tps` / `peak_tps_source` 键（值 None 或上述假象数），inert，schema 子集校验容忍，不做数据迁移；真要 TUI 级峰值须换细粒度流 harness（如 mcode exec stream-json），不在本仓现有 harness 能力内。
- 现状：有效
