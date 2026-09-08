# Grammar 内容架构

## 目标

`/grammar` 永远只使用一个阅读器页面。目录、正文、练习、图片和答案均来自数据库；新增 Unit 不新增 Vue 页面，也不保存 Unit 专属 HTML 或 CSS。

## 数据来源

- `grammar_books`：书籍与版本。
- `grammar_units`：Unit 标题、顺序、来源页和发布状态；同时作为当前目录的数据源。
- `grammar_content_blocks`：正文中的有序语义区块。
- `grammar_media`：正文和练习使用的图片。
- `grammar_exercises`：练习组及练习类型。
- `grammar_questions`：题目内容与题目类型。
- `grammar_answer_slots`：题目中的一个或多个作答位置。
- `grammar_answer_key_entries`：原书完整 `Key to Exercises` 答案索引；以书籍、Unit、练习号和题号作为稳定键，可先于正文和题目导入。
- `grammar_solutions` / `grammar_answer_variants`：标准答案及可接受变体，不随阅读接口发送给前端。

当前不需要单独的目录表。只有将来要支持 Part、Chapter 或自定义目录分组时，才增加 `grammar_sections`，由 Unit 关联分组。

## 前端约束

前端维护一个统一阅读器和一组可复用渲染组件：

- 正文类型：段落、模块首句、例句、公式表、提示框、图片、对话、分栏。
- 练习类型：行内填空、整句改写、匹配、选择、多空题、图片题、开放回答。

数据库保存内容、语义类型和有限的布局提示，例如 `media-right`、`two-columns`、`compact-table`。数据库不保存 `<style>`、任意 CSS 或任意 HTML。

遇到新题型时，只新增一次通用渲染组件；所有使用该题型的 Unit 都复用它。不能为单个 Unit 添加条件分支或独立页面。

## 导入流程

目标流程如下：

1. 从已经生成的 PDF 缓存读取指定 Unit 的文字、坐标和图片。
2. 生成一个符合 `schemas/grammar-unit.schema.json` 的版本化 Unit 数据包。
3. 人工核对标题、区块边界、题目和图片；答案默认从已经导入的 `grammar_answer_key_entries` 自动关联。
4. 通用导入器在单个数据库事务中写入所有相关表；只有印刷示例或需要人工拆分的复杂多空答案才需要在 Unit 数据包中附带答案结构。
5. 自动验证区块数、题目数、答案槽、图片和来源页。
6. 先保存为 `reviewed`，网页验收后改为 `published`；目录只返回 `published` Unit。

导入应支持重复执行。使用稳定业务键（书籍版本 + Unit 编号 + 练习编号 + 题号 + 答案槽）恢复浏览器草稿，不依赖数据库自增 ID。

## 当前完成度

- 数据库表、数据库目录接口、统一阅读器和 Unit 1 数据已可用。
- 静态 Unit 1–5 目录和静态页面回退已移除。
- Unit 1 和 Unit 2 已迁移为 `storage/grammar/import-packages/unit-NNN.json` 数据包，并由同一个导入器校验和写入；两者均已发布到数据库目录。
- 原书 PDF 第 348–379 页（印刷页 336–367）的完整 `Key to Exercises` 已导入：145 个 Unit、566 个练习小节、3941 条答案；现有 Unit 1–2 的非示例题均已建立答案外键关联。
- PDF 页面资源脚本按数据包引用的页码生成资产，不再写死 Unit 范围。
- 正文目前以 PDF 文本块重排；复杂表格和分栏仍需补充语义区块类型。
- 前端已支持图片填空、匹配、整句改写、普通行内填空和一句多答案槽；其他新题型按类型增加一次通用渲染器。

Unit 2 已完成端到端验证，包括正文分区、图片、五组练习，以及一道题包含多个答案槽。后续 Unit 若出现尚未支持的正文或练习类型，应增加可复用类型，而不是增加 Unit 专属页面或条件分支。
