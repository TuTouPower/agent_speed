# Task review t003（reviewer_focus: 通用）

- task：`t003_latest_json_report`
- spec：`docs/tasks/t003_latest_json_report/spec.md`
- diff_anchor：`122f59268ad6e13cbe90fb1ea52858039b14a66e`
- target：`git -C '/Users/karson/kar/code/agent_speed_t003' diff 122f59268ad6e13cbe90fb1ea52858039b14a66e`
- round：1
- reviewed_at：2026-09-22 14:15 UTC+8

## Findings 概览

无（Clean review，0 条 blocking finding）。

## 契约核验 (AC-001 ~ AC-007)

1. **AC-001（最新 batch 判定）**: PASS

    - 在 `src/agent_speed/report.py` 中按记录时序收集，以 `records[-1].get("batch_id")` 严格锁定每个格子的最新批次。
    - 过滤与统计仅在 `batch_records` 内展开，更早 batch 彻底排除，不参与统计亦不进行补位。

2. **AC-002（2 次有效上站门槛）**: PASS

    - 严格判断 `len(valid_calls) < 2`，不满足直接 `continue` 跳过，不上站。
    - 输入文件 `results.jsonl` 以只读方式打开，不修改、不剔除原始记录。

3. **AC-003（500 token 过滤与失败剔除）**: PASS

    - 逐条调用记录过滤要求 `status == "success"`、`out_tokens >= 500` 且 `wall > 0`。
    - 极短样本（< 500 tokens）与未成功的调用（含重试仍失败）均被准确丢弃，不计入有效次数。

4. **AC-004（输入 token 半数门槛）**: PASS

    - 提取最新批次有效调用的 `cl100k_tokens`（缺省兜底 200,000），计算账单输入 token 中位数 `in_toks_median`。
    - 判定 `in_toks_median < (cl100k / 2.0)`，严格小于切片一半时整格排除不上站。

5. **AC-005（codex 无生成窗口处理）**: PASS

    - codex 格子无生成窗口时，`gen_list` 为空列表，`gen_median` 设为 `None`。
    - 序列化后 `gen_tps` 输出为 JSON `null`，且 codex 格子在满足有效调用与输入门槛后正常上站。

6. **AC-006（降序覆盖写与全字段结构）**: PASS

    - 字典包含全部 13 个规定字段：`scenario`, `model`, `effort`, `source`, `harness`, `valid_reps`, `e2e_tps`, `gen_tps`, `ttft`, `out_tokens`, `in_tokens`, `batch_id`, `generated_at`。
    - 结果列表按 `e2e_tps` 降序排序（`reverse=True`），以 `json.dumps(indent=2)` 幂等覆盖写 `latest.json`，行数等于上站格子数。

7. **AC-007（仅由有效次数计算中位数）**: PASS

    - `e2e_tps`、`gen_tps`、`ttft`、`out_tokens`、`in_tokens` 的统计推导均限定在 `valid_calls` 列表，无效样本完全不干扰中位数计算。

## 结论

- 前轮 finding 复核：首轮审查，无前轮 finding
- 本轮新发现：0 条（clean review，无 blocking finding）
- 未进表的提示：
    - `src/agent_speed/report.py` 中定义的函数 `calculate_median` 未在 `generate_latest_json` 内部直接调用（内部因各字段精度及默认值差异直接调用了 `statistics.median` + `round`），属冗余工具函数，不影响功能正确性。
    - `tests/test_report.py` 覆盖了主流程，后续可根据需要进一步补充 `out_tokens == 500` 与 `in_tokens == cl100k / 2` 的临界边界单测。
- 总体判断：实现干净精确，完全满足 AC-001 ~ AC-007 验收标准，单测与契约门禁全部通过，同意 PASS。
- 系统性 follow-up：无

### AC 复验方式

- AC-001：`re_verified`。构造多 batch 样本（旧 batch 完整合格、最新 batch 仅 1 次有效），验证 `generate_latest_json` 严格丢弃历史 batch、不予补位，输出排除该格子。
- AC-002：`re_verified`。构造有效调用次数分别为 0、1、2、3 的用例，确认仅 >= 2 次者上站；核验 `results.jsonl` 文件未受任何写操作，行数与内容原样保留。
- AC-003：`re_verified`。独立测试临界值：499 token 判定无效被剔除，500 token 判定有效；同时验证 `status != "success"` 及 `wall <= 0` 的样本均被完全排除。
- AC-004：`re_verified`。以 `cl100k_tokens=200000` 验证账单输入临界值：99999 tokens 严格触发半数门槛被排除，100000 tokens（恰好一半）及以上正常通过。
- AC-005：`re_verified`。构造 codex 模拟数据（`decode_window` 与 `gen_tps` 均为 `None`），确认成功上站且输出对象中 `"gen_tps": null`。
- AC-006：`re_verified`。预置包含脏数据的 `latest.json` 后执行生成，确认旧文件被彻底覆盖覆写；输出 JSON 列表长度与上站格子数一致，包含全量 13 个字段，并严格按 `e2e_tps` 降序排列。
- AC-007：`re_verified`。在同一 batch 中混合无效样本（超短 400 tokens 畸高 TPS、失败调用）与有效样本，验证最终 `e2e_tps` 与 `out_tokens` 中位数均严格由有效调用计算，未被脏样本污染。

coverage = 7 / 7 = 100%

reviewed_scope: 0a610687b0e2effe

verdict: PASS
