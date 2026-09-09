# Grammar 确定性判题规则

## 目标

确定性判题必须可重复、可解释、可追溯。系统宁可返回“需进一步审核”，也不能用模糊相似度、自动纠错或推测答案把错误作答判成正确。

## 数据边界

- 只判定已发布 Unit 中 active、非示例题和 active 答案槽。
- 只有 `verification_status=verified` 的 solution 可以自动判题。
- 每次正式提交创建一条 `grammar_attempt_sessions`，每道题创建一条 `grammar_attempt_answers`。
- 正式记录保存题目、答案变体、用户原始输入、规范化输入、评分和 SHA-256 快照；以后教材或答案更新不会重写历史结果。
- 草稿继续保留。正式提交是复制当前答案快照，不是移动或清空草稿。

## 匹配规则

判题以完整 `grammar_answer_variants.values_json` 为单位。一道多空题只有所有答案槽同时匹配同一个 variant 才能判为正确，禁止从不同 variant 中分别挑选槽值组合。

`english-text + normalized` 只忽略不会改变答案含义的显示差异：

- Unicode 全角/兼容字符；
- 直引号与弯引号的字形差异；
- 首尾空白、重复空白；
- 标点前多余空格；
- 英文大小写；
- 省略答案原本已有的句末句号、问号或感叹号。

系统不会自动修正或忽略：

- 拼写错误；
- 单词顺序；
- 缺少或多出单词、冠词、介词、助动词；
- 肯定、否定、时态或人称变化；
- 缩写与完整形式。两者都正确时，必须在 `grammar_answer_variants` 中显式列出；
- 把答案要求的句末标点替换为另一种标点，或给原本没有终止标点的答案额外添加标点；
- 内部标点造成的含义差异。

`choice-code + exact` 只接受对应选项代码，忽略代码的大小写和首尾空白，不接受 `option e` 等额外文本。

## 判题结果

- `correct`：完整命中一个已审核 variant。
- `incorrect`：已完整作答，但未命中任何完整 variant。
- `incomplete`：多空题只填写了部分答案槽。
- `unanswered`：该题所有答案槽均为空。
- `needs_review`：答案规则未审核、缺失、结构不完整或使用系统不支持的规则，不能安全自动判定。

只有 `correct` 获得该题全部分数。第一版不进行推测性的部分给分。

## API

提交：

```http
POST /api/grammar/library/units/1/submissions
Content-Type: application/json

{
  "answers": [
    {"slot_id": 217, "value": "He's tying"}
  ],
  "question_versions": [
    {"question_id": 218, "version": "由阅读接口返回的 64 位版本指纹"}
  ]
}
```

未包含的有效答案槽按空答案处理。未知、停用、示例题或其他 Unit 的答案槽会拒绝整个请求，不生成部分提交记录。`question_versions` 必须完整匹配当前页面的题目和答案槽结构；页面打开后若 Unit 被重新导入或修改，提交会要求刷新，避免使用旧页面误判。

读取历史快照：

```http
GET /api/grammar/library/submissions/1
```

当前个人部署使用 `GRAMMAR_DRAFT_PROFILE` 隔离读取权限；增加登录后应替换为认证用户 ID。
