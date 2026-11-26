# Sample Bug Report — Negative HP

This report was produced by an actual 8-step demo run. The LLM provider returned HTTP 400 during analysis, and the deterministic fallback still caught the illegal game state.

- **Title:** 数值越界：hp=-3（规则兜底判定）
- **Severity:** high
- **Category:** logic
- **Expected:** 数值应处于合法范围（HP 等不应小于 0），界面操作应有响应
- **Actual:** hp=-3
- **Reproduction:** [战斗循环] click:攻击

## Evidence

规则兜底：负数、NaN/undefined 或无响应属于明确异常状态
[步骤8复核] 检测到非法游戏状态：hp=-3；LLM分析失败(LLM 调用失败: Client error '400 Bad Request' for url 'https://token.sensenova.cn/v1/chat/completions'
For more information check: https://developer.mozilla.org/en-US/docs/Web/HTTP/Status/400)，使用规则兜底
