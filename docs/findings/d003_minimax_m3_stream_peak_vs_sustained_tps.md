# d003 MiniMax-M3 在 200K 下 TUI 实时显示约 200 tok/s 是秒级突发峰值，整轮平均仅约 88 tok/s，两者皆真但统计窗口不同

- 来源：日常（mcode 0.5.2 直连 MiniMax-M3 api-key 单次 200K 探测，prompt + Django 切片共 971,818 字符）
- 结论：同一轮 runs 中 1s 滚动峰值约 187 tok/s、正文段平均约 92 tok/s、榜单整窗生成 TPS 87.8、端到端 76.3；TUI 显示的是前者，榜单记录的是后两者，不存在测速错误。
- 证据：stream-json 全量日志（628 行）时间线：wall 91.33s，其中本地启动 1.42s、prefill 致 TTFT 9.60s（输入 215,260 tok）、推理链 3.28s（约 479 tok，约 146 tok/s）、正文 12.88→88.93s（76.05s，595 个增量块，约 6,488 tok）、收尾 2.38s；正文段内大于 0.5s 的流间停顿共 12.3s（含一笔 4.93s），剔除停顿后活跃吐词约 109 tok/s，1s/2s/5s 滚动峰值分别为约 187/155/133 tok/s；服务端 `turn.completed.durationMs=87824` 折算约 79.3 tok/s，与客户端整窗一致。
- 影响：后续若新增 minimax-code harness，其生成 TPS 定义须与现有契约对齐（正文段整窗平均，而非滚动峰值），否则与 opencode/codex/kimi 格子不可比；向用户解释榜单与 TUI 体感差异时引用本条。
- 现状：有效
