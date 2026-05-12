#!/usr/bin/env python3
"""
セミナーコメント集計ツール
Manaba コメントCSV → 発表者別CSV 分割ツール
"""
from __future__ import annotations

import csv
import io
import os
import random
import re
import sys
import webbrowser
import zipfile
from pathlib import Path
from tkinter import filedialog, messagebox
import tkinter as tk
import customtkinter as ctk

# ── Optional drag-and-drop (for files) ───────────────────────
try:
    from tkinterdnd2 import DND_FILES, TkinterDnD

    class _Root(ctk.CTk):
        def __init__(self, *a, **kw):
            super().__init__(*a, **kw)
            TkinterDnD._require(self)

    HAS_DND = True
except Exception:
    _Root = ctk.CTk
    HAS_DND = False

# ── App metadata ─────────────────────────────────────────────
APP_NAME    = "セミナーコメント集計ツール"
VERSION     = "1.0.0"
AUTHOR      = "Genki Sasaki"
# TODO: update to actual repository URL after creating the GitHub repo
GITHUB_URL  = "https://github.com/GenSSK/Semminer-Comment-Splitter"

# ── Internal regex constants ──────────────────────────────────
_ID_RE = re.compile(r"^[0-9]{2}[A-Za-z]{1,5}[0-9]{1,3}$")
# Matches first lines like "発表者", "発表者本人", "本人", "本人です。"
_SELF_LINE_RE = re.compile(r"^(発表者|本人)")

# ── Data layer ────────────────────────────────────────────────


def _clean(text: str) -> str:
    """Remove a student-ID prefix line from the start of a comment."""
    lines = text.split("\n") if text else []
    if lines and _ID_RE.match(lines[0].strip()):
        lines = lines[1:]
    return "\n".join(lines).strip()


def load_zip(path: str) -> tuple[list[dict], str | None]:
    """Parse comments.csv from a Manaba ZIP export. Returns (rows, error|None)."""
    try:
        with zipfile.ZipFile(path) as zf:
            csv_name = next(
                (n for n in zf.namelist()
                 if "comments.csv" in n and "sjis" not in n.lower()),
                None,
            )
            if not csv_name:
                return [], "ZIP に comments.csv が見つかりません"
            raw = zf.read(csv_name).decode("utf-8-sig")
    except Exception as exc:
        return [], f"ZIP 読み込みエラー: {exc}"

    all_rows = list(csv.reader(io.StringIO(raw)))
    hdr_idx = next((i for i, r in enumerate(all_rows) if r and "氏名" in r), None)
    if hdr_idx is None:
        return [], "ヘッダー行（氏名）が見つかりません"

    hdr = [h.strip() for h in all_rows[hdr_idx]]

    def _col(name: str) -> int | None:
        try:
            return hdr.index(name)
        except ValueError:
            return None

    cols = {
        "name": _col("氏名"),
        "uid":  _col("ユーザ ID"),
        "qno":  _col("Q.No"),
        "cmt":  _col("report/answer"),
        "date": _col("提出日"),
    }
    missing = [k for k, v in cols.items() if v is None and k != "date"]
    if missing:
        return [], f"必要な列が見つかりません: {missing}  ヘッダー: {hdr}"

    def _get(row: list, key: str) -> str:
        idx = cols[key]
        return row[idx].strip() if idx is not None and idx < len(row) else ""

    rows = []
    for row in all_rows[hdr_idx + 1:]:
        if not (_get(row, "name") or _get(row, "uid")):
            continue
        rows.append({
            "氏名":    _get(row, "name"),
            "UID":     _get(row, "uid"),
            "QNo":     _get(row, "qno"),
            "コメント": _get(row, "cmt"),
            "提出日":  _get(row, "date"),
        })
    return rows, None


def detect_presenters(rows: list[dict]) -> list[dict]:
    """
    Infer which student presented at each Q.No.
    Detection signals (checked in order):
      1. Blank comment
      2. First line matches student's own ID (case-insensitive)
      3. First line starts with 発表者 or 本人
      4. Comment contains 発表者は自分
    """
    qnos = sorted({r["QNo"] for r in rows if r["QNo"].isdigit()}, key=int)
    result = []
    for qno in qnos:
        found: tuple[str, str] | None = None
        for r in (x for x in rows if x["QNo"] == qno):
            cmt, uid = r["コメント"], r["UID"]
            if not cmt:
                found = (uid, r["氏名"]); break
            first = cmt.split("\n")[0].strip()
            if _ID_RE.match(first) and first.upper() == uid.upper():
                found = (uid, r["氏名"]); break
            if _SELF_LINE_RE.match(first):
                found = (uid, r["氏名"]); break
            if "発表者は自分" in cmt:
                found = (uid, r["氏名"]); break
        result.append({
            "qno":  qno,
            "uid":  found[0] if found else "",
            "name": found[1] if found else "",
        })
    return result


def make_csvs(rows: list[dict], presenters: list[dict], out_dir: str) -> tuple[list[str], list[str]]:
    """Write one CSV per presenter. Returns (created_paths, error_msgs)."""
    ok, errs = [], []
    for p in presenters:
        qno, uid, name = p["qno"], p["uid"].strip(), p["name"].strip()
        if not uid and not name:
            errs.append(f"発表者 {qno}: 未設定のためスキップ")
            continue
        comments = [
            _clean(r["コメント"])
            for r in rows
            if r["QNo"] == qno and r["UID"].upper() != uid.upper()
        ]
        comments = [c for c in comments if c]
        random.shuffle(comments)

        def _safe(s: str) -> str:
            return re.sub(r'[\\/:*?"<>|]', "_", s)

        fpath = os.path.join(out_dir, f"集計コメント_{_safe(uid)}_{_safe(name)}.csv")
        try:
            with open(fpath, "w", encoding="utf-8-sig", newline="") as f:
                w = csv.writer(f)
                w.writerow(["コメント"])
                w.writerows([c] for c in comments)
            ok.append(fpath)
        except Exception as exc:
            errs.append(f"発表者 {qno} 書き込みエラー: {exc}")
    return ok, errs


# ── UI ────────────────────────────────────────────────────────

ctk.set_appearance_mode("System")
ctk.set_default_color_theme("blue")


class _PresenterRow(ctk.CTkFrame):
    """One editable row in the presenter mapping table."""

    def __init__(self, master, qno: str, uid: str, name: str, on_del, drag_cbs=None, **kw):
        super().__init__(master, fg_color="transparent", **kw)

        # Drag handle — binds to row-reorder callbacks
        self.handle = ctk.CTkLabel(
            self, text="⠿", width=20, cursor="fleur",
            text_color=("gray55", "gray50"),
        )
        self.handle.pack(side="left", padx=(4, 0))

        # Presenter number (fixed — only uid/name are swapped on drag)
        ctk.CTkLabel(self, text=qno, width=32, anchor="e").pack(side="left", padx=(2, 6))

        self._uid_var = tk.StringVar(value=uid)
        self._name_var = tk.StringVar(value=name)
        ctk.CTkEntry(
            self, textvariable=self._uid_var, placeholder_text="学籍番号", width=112,
        ).pack(side="left", padx=3)
        ctk.CTkEntry(
            self, textvariable=self._name_var, placeholder_text="氏名", width=160,
        ).pack(side="left", padx=3)

        self.del_btn = ctk.CTkButton(
            self, text="×", width=28,
            fg_color="transparent",
            text_color=("gray50", "gray55"),
            hover_color=("gray85", "gray30"),
            command=on_del,
        )
        self.del_btn.pack(side="left", padx=2)

        self.qno = qno

        if drag_cbs:
            on_start, on_motion, on_end = drag_cbs
            self.handle.bind("<Button-1>",        lambda e: on_start(self, e))
            self.handle.bind("<B1-Motion>",        lambda e: on_motion(self, e))
            self.handle.bind("<ButtonRelease-1>",  lambda e: on_end(self, e))

    def get(self) -> dict:
        return {"qno": self.qno, "uid": self._uid_var.get(), "name": self._name_var.get()}


# ── Main window ───────────────────────────────────────────────

class App(_Root):

    def __init__(self):
        super().__init__()
        self.title("セミナーコメント集計ツール")
        self.geometry("680x740")
        self.minsize(560, 580)

        self._rows: list[dict] = []
        self._zip_var = tk.StringVar()
        self._out_var = tk.StringVar()
        self._tbl_rows: list[_PresenterRow] = []
        self._next_qno = 1

        # Row-reorder drag state
        self._drag_src: _PresenterRow | None = None
        self._drag_tgt: _PresenterRow | None = None

        # Output subfolder option
        self._subfolder_var = tk.BooleanVar(value=True)

        self._setup_menu()
        self._build()

    # ── Menu & About ─────────────────────────────────────────

    def _setup_menu(self):
        menubar = tk.Menu(self)
        if sys.platform == "darwin":
            # macOS: items added to name='apple' appear in the app-name menu
            apple = tk.Menu(menubar, name="apple", tearoff=0)
            menubar.add_cascade(menu=apple)
            apple.add_command(label=f"About {APP_NAME}", command=self._show_about)
        else:
            # Windows / Linux: conventional Help menu
            help_menu = tk.Menu(menubar, tearoff=0)
            menubar.add_cascade(label="ヘルプ(H)", menu=help_menu)
            help_menu.add_command(label="バージョン情報...", command=self._show_about)
        self.configure(menu=menubar)

    def _show_about(self):
        dlg = ctk.CTkToplevel(self)
        dlg.title("バージョン情報")
        dlg.geometry("420x300")
        dlg.resizable(False, False)
        dlg.transient(self)
        dlg.grab_set()
        dlg.focus_set()

        ctk.CTkLabel(
            dlg, text=APP_NAME,
            font=ctk.CTkFont(size=17, weight="bold"),
        ).pack(pady=(28, 4))
        ctk.CTkLabel(dlg, text=f"Version {VERSION}").pack()
        ctk.CTkLabel(dlg, text=f"© 2026 {AUTHOR}").pack(pady=(14, 2))
        ctk.CTkLabel(dlg, text="License: MIT").pack()

        link = ctk.CTkLabel(
            dlg, text=GITHUB_URL,
            text_color=("#1D6FD1", "#6BBBF7"),
            cursor="hand2",
        )
        link.pack(pady=(12, 0))
        link.bind("<Button-1>", lambda _e: webbrowser.open(GITHUB_URL))

        ctk.CTkButton(dlg, text="閉じる", width=100, command=dlg.destroy).pack(pady=24)

    # ── Layout helpers ───────────────────────────────────────

    def _section(self, title: str, btn_label: str | None = None, btn_cmd=None) -> ctk.CTkFrame:
        outer = ctk.CTkFrame(self)
        outer.pack(fill="x", padx=16, pady=6)
        hrow = ctk.CTkFrame(outer, fg_color="transparent")
        hrow.pack(fill="x", padx=12, pady=(8, 2))
        ctk.CTkLabel(hrow, text=title, font=ctk.CTkFont(weight="bold")).pack(side="left")
        if btn_label:
            ctk.CTkButton(hrow, text=btn_label, width=90, command=btn_cmd).pack(side="right")
        return outer

    def _build(self):
        ctk.CTkLabel(
            self, text="セミナーコメント集計ツール",
            font=ctk.CTkFont(size=18, weight="bold"),
        ).pack(pady=(16, 4))

        # ── Step 1: ZIP ──────────────────────────────────────
        sec1 = self._section("① ZIPファイル")
        self._drop_zone = ctk.CTkFrame(
            sec1, height=76, border_width=2,
            border_color=("gray55", "gray45"), corner_radius=8,
        )
        self._drop_zone.pack(fill="x", padx=12, pady=(4, 2))
        self._drop_zone.pack_propagate(False)

        drop_hint = (
            "ZIPをここにドロップ  /  下のボタンから選択" if HAS_DND
            else "下のボタンからZIPを選択してください"
        )
        self._drop_lbl = ctk.CTkLabel(
            self._drop_zone, text=drop_hint,
            text_color=("gray45", "gray60"),
        )
        self._drop_lbl.place(relx=0.5, rely=0.5, anchor="center")

        if HAS_DND:
            for widget in (self._drop_zone, self._drop_lbl):
                widget.drop_target_register(DND_FILES)
                widget.dnd_bind("<<Drop>>", self._on_drop)

        row1 = ctk.CTkFrame(sec1, fg_color="transparent")
        row1.pack(fill="x", padx=12, pady=(2, 10))
        ctk.CTkButton(row1, text="ZIPを選択…", width=120, command=self._browse_zip).pack(side="left")
        ctk.CTkLabel(
            row1, textvariable=self._zip_var, anchor="w",
            text_color=("gray40", "gray65"),
        ).pack(side="left", padx=10, fill="x", expand=True)

        # ── Step 2: Presenter table ──────────────────────────
        sec2 = self._section("② 発表者リスト（自動検出 / 編集可）", "＋行追加", self._add_row)

        col_hdr = ctk.CTkFrame(sec2, fg_color="transparent")
        col_hdr.pack(fill="x", padx=12)
        # Spacers to align with handle + number in each row
        ctk.CTkLabel(col_hdr, text="", width=24).pack(side="left", padx=(4, 0))
        ctk.CTkLabel(
            col_hdr, text="番号", width=32, anchor="e",
            font=ctk.CTkFont(size=11), text_color=("gray45", "gray60"),
        ).pack(side="left", padx=(2, 6))
        for lbl, w in [("学籍番号", 112), ("氏名", 160)]:
            ctk.CTkLabel(
                col_hdr, text=lbl, width=w, anchor="w",
                font=ctk.CTkFont(size=11), text_color=("gray45", "gray60"),
            ).pack(side="left", padx=3)

        self._tbl = ctk.CTkScrollableFrame(sec2, height=200)
        self._tbl.pack(fill="x", padx=12, pady=(2, 10))

        # ── Step 3: Output dir ───────────────────────────────
        sec3 = self._section("③ 出力先フォルダ")
        row3 = ctk.CTkFrame(sec3, fg_color="transparent")
        row3.pack(fill="x", padx=12, pady=(2, 4))
        ctk.CTkButton(row3, text="フォルダを選択…", width=140, command=self._browse_out).pack(side="left")
        ctk.CTkLabel(
            row3, textvariable=self._out_var, anchor="w",
            text_color=("gray40", "gray65"),
        ).pack(side="left", padx=10, fill="x", expand=True)
        ctk.CTkCheckBox(
            sec3, text="サブフォルダを作成（ZIPファイル名_集計コメント）",
            variable=self._subfolder_var,
        ).pack(anchor="w", padx=14, pady=(0, 10))

        # ── Run ──────────────────────────────────────────────
        ctk.CTkButton(
            self, text="集計を実行", height=46,
            font=ctk.CTkFont(size=15, weight="bold"),
            command=self._run,
        ).pack(pady=6)

        # ── Log ──────────────────────────────────────────────
        ctk.CTkLabel(self, text="ログ", anchor="w").pack(anchor="w", padx=16)
        self._log = ctk.CTkTextbox(self, height=110, state="disabled")
        self._log.pack(fill="both", expand=True, padx=16, pady=(0, 14))

    # ── Row drag-and-drop (swap uid/name between fixed slots) ─

    def _drag_start(self, row: _PresenterRow, event):
        self._drag_src = row
        self._drag_tgt = None

    def _drag_motion(self, row: _PresenterRow, event):
        abs_y = event.widget.winfo_rooty() + event.y
        new_tgt = self._row_at_y(abs_y)
        if new_tgt is self._drag_src:
            new_tgt = None

        if new_tgt is not self._drag_tgt:
            if self._drag_tgt and self._drag_tgt.winfo_exists():
                self._drag_tgt.configure(fg_color="transparent")
            self._drag_tgt = new_tgt
            if new_tgt:
                new_tgt.configure(fg_color=("#BFDBFE", "#1E40AF"))

    def _drag_end(self, row: _PresenterRow, event):
        if self._drag_tgt and self._drag_tgt.winfo_exists():
            self._drag_tgt.configure(fg_color="transparent")

        abs_y = event.widget.winfo_rooty() + event.y
        tgt = self._row_at_y(abs_y)

        if tgt and tgt is not self._drag_src and tgt.winfo_exists():
            # Swap uid and name; slot numbers stay fixed
            su, sn = self._drag_src._uid_var.get(), self._drag_src._name_var.get()
            tu, tn = tgt._uid_var.get(), tgt._name_var.get()
            self._drag_src._uid_var.set(tu)
            self._drag_src._name_var.set(tn)
            tgt._uid_var.set(su)
            tgt._name_var.set(sn)

        self._drag_src = None
        self._drag_tgt = None

    def _row_at_y(self, abs_y: int) -> _PresenterRow | None:
        for r in self._tbl_rows:
            if not r.winfo_exists():
                continue
            try:
                top = r.winfo_rooty()
                if top <= abs_y < top + r.winfo_height():
                    return r
            except Exception:
                pass
        return None

    # ── File / ZIP handlers ──────────────────────────────────

    def _on_drop(self, event):
        path = event.data.strip().strip("{}")
        if path.lower().endswith(".zip"):
            self._load_zip(path)
        else:
            self._log_msg("⚠ ZIPファイルをドロップしてください")

    def _browse_zip(self):
        p = filedialog.askopenfilename(
            title="ZIPファイルを選択",
            filetypes=[("ZIP", "*.zip"), ("All", "*.*")],
        )
        if p:
            self._load_zip(p)

    def _load_zip(self, path: str):
        self._log_msg(f"読み込み中: {Path(path).name} …")
        rows, err = load_zip(path)
        if err:
            self._log_msg(f"❌ {err}")
            messagebox.showerror("エラー", err)
            return

        self._rows = rows
        self._zip_var.set(Path(path).name)
        if not self._out_var.get():
            self._out_var.set(str(Path(path).parent))

        presenters = detect_presenters(rows)
        self._reload_table(presenters)
        n = sum(1 for p in presenters if p["uid"] or p["name"])
        self._log_msg(f"✅ {len(rows)} 件読み込み、発表者 {n}/{len(presenters)} 件自動検出")

    def _browse_out(self):
        d = filedialog.askdirectory(title="出力先フォルダを選択")
        if d:
            self._out_var.set(d)

    # ── Table management ─────────────────────────────────────

    def _reload_table(self, presenters: list[dict]):
        for w in self._tbl_rows:
            w.destroy()
        self._tbl_rows.clear()
        for p in presenters:
            self._insert_row(p["qno"], p["uid"], p["name"])
        self._next_qno = (int(presenters[-1]["qno"]) + 1) if presenters else 1

    def _add_row(self):
        self._insert_row(str(self._next_qno))
        self._next_qno += 1

    def _insert_row(self, qno: str, uid: str = "", name: str = ""):
        drag_cbs = (self._drag_start, self._drag_motion, self._drag_end)
        row = _PresenterRow(self._tbl, qno, uid, name, on_del=None, drag_cbs=drag_cbs)
        row.del_btn.configure(command=lambda r=row: self._del_row(r))
        row.pack(fill="x", pady=2)
        self._tbl_rows.append(row)

    def _del_row(self, row: _PresenterRow):
        row.destroy()
        self._tbl_rows = [r for r in self._tbl_rows if r.winfo_exists()]

    # ── Run ──────────────────────────────────────────────────

    def _run(self):
        if not self._rows:
            messagebox.showwarning("未読み込み", "ZIPファイルを先に読み込んでください")
            return
        out = self._out_var.get().strip()
        if not out or not os.path.isdir(out):
            messagebox.showerror("エラー", "有効な出力先フォルダを選択してください")
            return
        if self._subfolder_var.get():
            zip_stem = Path(self._zip_var.get()).stem
            out = os.path.join(out, f"{zip_stem}_集計コメント")
            os.makedirs(out, exist_ok=True)
            self._log_msg(f"📁 サブフォルダ作成: {Path(out).name}")
        presenters = [r.get() for r in self._tbl_rows if r.winfo_exists()]
        ok, errs = make_csvs(self._rows, presenters, out)
        for e in errs:
            self._log_msg(f"⚠ {e}")
        for p in ok:
            self._log_msg(f"✅ {Path(p).name}")
        self._log_msg(f"完了: {len(ok)} ファイル生成")
        if ok:
            messagebox.showinfo("完了", f"{len(ok)} 件の CSV を生成しました\n\n出力先: {out}")

    def _log_msg(self, msg: str):
        self._log.configure(state="normal")
        self._log.insert("end", msg + "\n")
        self._log.see("end")
        self._log.configure(state="disabled")
        self.update_idletasks()


def main():
    App().mainloop()


if __name__ == "__main__":
    main()
