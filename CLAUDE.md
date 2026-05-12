# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Purpose

This tool processes peer-review comment exports from the Japanese LMS (Manaba) for the course **電子システム工学セミナーⅠ**. The goal is to "split" the bulk comment CSV — where every student's comments for all presenters are mixed together — into per-presenter views so each presenter can see the feedback they received.

## Input Data

ZIP files are placed in `zip/`. Each ZIP (exported from Manaba) contains four files:

| File | Encoding | Contents |
|------|----------|----------|
| `comments.csv` | UTF-8 (BOM) | Simplified: 氏名, ユーザID, Q.No, コメント本文, 提出日, 成績, 点数 |
| `answer.csv` | UTF-8 (BOM) | Full: adds id, コース名, ダウンロードリンク, point, corrected_file |
| `comments-sjis.csv` | Shift-JIS | Same as comments.csv, alternate encoding |
| `answer-sjis.csv` | Shift-JIS | Same as answer.csv, alternate encoding |

Both CSVs have a 5-line metadata header before the column headers:
```
レポート/記述式問題の採点
<timestamp>
<assignment name>
contents_id,<hash>
<blank line>
<column headers>
```

### Key columns

- **Q.No** — identifies which presenter the comment is for (1 = presenter 1, 2 = presenter 2, …). This is the split key.
- **ユーザ ID** (or `USERID` in answer.csv) — the commenter's student ID (e.g. `26KMH01`)
- **氏名** — commenter's full name
- **report/answer** — the comment text. Some students prepend the target presenter's student ID on the first line before the actual comment body.

## Directory Structure

```
zip/          # Raw ZIP exports from Manaba (input)
              # ZIP filename encodes: assignment name + export timestamp
```

Output structure is not yet defined — to be determined when the tool is implemented.
