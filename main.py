import json
import random
import os
import tkinter as tk
from tkinter import ttk, messagebox

SETTINGS_FILE = "user_settings.json"
TUTORIAL_FILE = "tutorial.txt"
VERSION = "1.0.0"



# ================================
# 設定の読み込み
# ================================
def load_settings():
    if not os.path.exists(SETTINGS_FILE):
        return None

    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return None


# ================================
# 設定の保存
# ================================
def save_settings():
    data = {
        "owned_units": list(owned_units),
        "required_units": list(required_units),
        "discount_units": list(discount_units),
        "required_star_ranges": required_star_ranges,
        "options": {
            "weak_replace": enable_weak_replace,
            "cheapest_replace": enable_cheapest_replace,
            "discount_priority": enable_discount_priority
        }
    }

    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ================================
# JSON 読み込み
# ================================
with open("units.json", "r", encoding="utf-8") as f:
    units = json.load(f)

units_by_name = {u["name"]: u for u in units}

# ================================
# 設定データ（初期値）
# ================================
discount_units = set()
owned_units = set(unit["name"] for unit in units)
required_units = set()

required_star_ranges = {
    "5": False,
    "4-4.5": False,
    "3-3.5": False,
    "2-2.5": False,
    "0.5-1.5": False
}

enable_weak_replace = False
enable_cheapest_replace = False
enable_discount_priority = False

# ================================
# 設定ファイルの読み込み反映
# ================================
loaded = load_settings()
if loaded:
    owned_units = set(loaded.get("owned_units", []))
    required_units = set(loaded.get("required_units", []))
    discount_units = set(loaded.get("discount_units", []))
    required_star_ranges = loaded.get("required_star_ranges", required_star_ranges)

    opt = loaded.get("options", {})
    enable_weak_replace = opt.get("weak_replace", False)
    enable_cheapest_replace = opt.get("cheapest_replace", False)
    enable_discount_priority = opt.get("discount_priority", False)


# ================================
# ロジック部分
# ================================
STAR_RANGES = {
    "5": (5, 5),
    "4-4.5": (4, 4.5),
    "3-3.5": (3, 3.5),
    "2-2.5": (2, 2.5),
    "0.5-1.5": (0.5, 1.5)
}


def get_cost(unit):
    if unit["name"] in discount_units:
        return int(unit["leadership"] * 0.84)
    return unit["leadership"]


def recompute_remaining(selected, max_leadership):
    used = sum(u["leadership"] for u in selected)
    return max_leadership - used


def is_protected(entry):
    if entry["name"] in required_units:
        return True
    if entry.get("source") == "star_required":
        return True
    return False


def fill_strongest(selected, max_leadership):
    remaining = recompute_remaining(selected, max_leadership)
    used_names = {u["name"] for u in selected}

    candidates = [
        u for u in units
        if u["name"] in owned_units and u["name"] not in used_names
    ]

    candidates.sort(key=lambda u: get_cost(u), reverse=True)

    for unit in candidates:
        cost = get_cost(unit)
        if cost <= remaining:
            selected.append({
                "name": unit["name"],
                "leadership": cost,
                "star": unit["star"],
                "source": "upgrade"
            })
            remaining -= cost

    return selected


def post_process(selected, max_leadership):
    global enable_weak_replace, enable_cheapest_replace

    changed = False

    # 弱兵団置き換え
    if enable_weak_replace:
        for _ in range(30):
            low_indices = [
                i for i, u in enumerate(selected)
                if 0.5 <= u["star"] <= 1.5 and not is_protected(u)
            ]
            if len(low_indices) < 2:
                break

            changed = True

            idx1, idx2 = random.sample(low_indices, 2)
            for idx in sorted([idx1, idx2], reverse=True):
                selected.pop(idx)

            selected = fill_strongest(selected, max_leadership)

    # 最弱兵団置き換え
    if enable_cheapest_replace and not changed:
        removable = [
            (i, u) for i, u in enumerate(selected)
            if not is_protected(u)
        ]
        if removable:
            idx, _ = min(removable, key=lambda x: x[1]["leadership"])
            selected.pop(idx)
            selected = fill_strongest(selected, max_leadership)

    return selected


def generate_army(max_leadership):
    remaining = max_leadership
    selected = []
    selected_names = set()

    # 1. 必須兵団を優先的に入れる
    required_list = [
        u for u in units
        if u["name"] in required_units
        and u["name"] in owned_units
    ]
    random.shuffle(required_list)

    for unit in required_list:
        cost = get_cost(unit)
        if cost <= remaining and unit["name"] not in selected_names:
            selected.append({
                "name": unit["name"],
                "leadership": cost,
                "star": unit["star"],
                "source": "required"
            })
            remaining -= cost
            selected_names.add(unit["name"])

    # 2. 兵団ランク指定（ON の帯ごとに最低1つ入れる）
    for key, enabled in required_star_ranges.items():
        if not enabled:
            continue

        low, high = STAR_RANGES[key]

        # すでにこの帯の兵団が入っていればスキップ
        if any(low <= u["star"] <= high for u in selected):
            continue

        # 候補を作る（所持兵団のみ・未選択）
        candidates = [
            u for u in units
            if low <= u["star"] <= high
            and u["name"] in owned_units
            and u["name"] not in selected_names
        ]

        if not candidates:
            continue

        # ★ 統率軍魂優先の正しい処理
        if enable_discount_priority:
            random.shuffle(candidates)  # ランダム性を確保
            candidates.sort(
                key=lambda u: (u["name"] not in discount_units,)
            )
        else:
            random.shuffle(candidates)

        for unit in candidates:
            cost = get_cost(unit)
            if cost <= remaining:
                selected.append({
                    "name": unit["name"],
                    "leadership": cost,
                    "star": unit["star"],
                    "source": "star_required"
                })
                remaining -= cost
                selected_names.add(unit["name"])
                break

    # 3. 残りの統率値で、所持兵団からランダムに埋める
    while True:
        candidates = [
            u for u in units
            if u["name"] in owned_units
            and u["name"] not in selected_names
        ]

        if not candidates:
            break

        # ★ 統率軍魂優先の正しい処理（こちらも同じ）
        if enable_discount_priority:
            random.shuffle(candidates)
            candidates.sort(
                key=lambda u: (u["name"] not in discount_units,)
            )
        else:
            random.shuffle(candidates)

        picked = False
        for unit in candidates:
            cost = get_cost(unit)
            if cost <= remaining:
                selected.append({
                    "name": unit["name"],
                    "leadership": cost,
                    "star": unit["star"],
                    "source": "normal"
                })
                remaining -= cost
                selected_names.add(unit["name"])
                picked = True
                break

        if not picked:
            break

    total = sum(u["leadership"] for u in selected)
    return selected, total


# ================================
# UI（ttk版）
# ================================
def on_generate():
    try:
        max_leadership = int(entry.get())
    except ValueError:
        messagebox.showerror("エラー", "統率値は数字で入力してください")
        return

    result, total = generate_army(max_leadership)

    # ここで詳細オプション（弱兵団置き換え・最弱置き換え）を適用
    result = post_process(result, max_leadership)
    total = sum(u["leadership"] for u in result)

    text.delete("1.0", tk.END)
    text.insert(tk.END, "--- ランダム編成結果 ---\n")
    for unit in result:
        text.insert(
            tk.END,
            f"- {unit['name']}（{unit['leadership']} / ★{units_by_name[unit['name']]['star']}）\n"
        )
    text.insert(tk.END, f"\n合計統率値: {total}/{max_leadership}\n")



# ================================
# チェックボックス画面（検索付き）
# ================================
def open_checkbox_window(title, target_set):
    win = tk.Toplevel(root)
    win.title(title)

    frame = ttk.Frame(win, padding=10)
    frame.pack(fill="both", expand=True)

    # 検索バー
    search_frame = ttk.Frame(frame)
    search_frame.pack(fill="x", pady=(0, 5))
    ttk.Label(search_frame, text="兵団検索:").pack(side="left")
    search_var = tk.StringVar()
    search_entry = ttk.Entry(search_frame, textvariable=search_var, width=25)
    search_entry.pack(side="left", padx=5)

    # スクロール領域
    canvas = tk.Canvas(frame)
    scrollbar = ttk.Scrollbar(frame, orient="vertical", command=canvas.yview)
    scroll_frame = ttk.Frame(canvas)

    scroll_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
    canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
    canvas.configure(yscrollcommand=scrollbar.set)

    canvas.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")

    check_vars = {}
    checkbuttons = {}

    def rebuild_list():
        for cb in checkbuttons.values():
            cb.destroy()
        checkbuttons.clear()

        keyword = search_var.get().strip().lower()

        for unit in units:
            name = unit["name"]
            if keyword and keyword not in name.lower():
                continue

            if name not in check_vars:
                check_vars[name] = tk.BooleanVar(value=(name in target_set))

            var = check_vars[name]
            cb = ttk.Checkbutton(scroll_frame, text=name, variable=var)
            cb.pack(anchor="w")
            checkbuttons[name] = cb

    def on_search(*args):
        rebuild_list()

    search_var.trace_add("write", on_search)

    rebuild_list()

    def save():
        target_set.clear()
        for name, var in check_vars.items():
            if var.get():
                target_set.add(name)
        win.destroy()

    ttk.Button(frame, text="保存", command=save).pack(pady=5)


# ================================
# 兵団ランク指定
# ================================
def open_star_required_window():
    win = tk.Toplevel(root)
    win.title("兵団ランク指定")

    frame = ttk.Frame(win, padding=10)
    frame.pack(fill="both", expand=True)

    check_vars = {}

    for key in required_star_ranges:
        var = tk.BooleanVar(value=required_star_ranges[key])
        check_vars[key] = var
        ttk.Checkbutton(frame, text=key, variable=var).pack(anchor="w")

    def save():
        for key, var in check_vars.items():
            required_star_ranges[key] = var.get()
        win.destroy()

    ttk.Button(frame, text="保存", command=save).pack(pady=5)
def open_final_adjust_window():
    global enable_weak_replace, enable_cheapest_replace, enable_discount_priority

    win = tk.Toplevel(root)
    win.title("詳細オプション")

    frame = ttk.Frame(win, padding=10)
    frame.pack(fill="both", expand=True)

    var_weak = tk.BooleanVar(value=enable_weak_replace)
    var_cheapest = tk.BooleanVar(value=enable_cheapest_replace)
    var_discount = tk.BooleanVar(value=enable_discount_priority)

    ttk.Checkbutton(
        frame,
        text="弱兵団置き換え（★0.5〜1.5が2体以上）",
        variable=var_weak
    ).pack(anchor="w")

    ttk.Checkbutton(
        frame,
        text="最弱兵団を外して強兵団に置き換え",
        variable=var_cheapest
    ).pack(anchor="w")

    ttk.Checkbutton(
        frame,
        text="統率軍魂付きの兵団を優先して選択する",
        variable=var_discount
    ).pack(anchor="w")

    def save():
        globals()["enable_weak_replace"] = var_weak.get()
        globals()["enable_cheapest_replace"] = var_cheapest.get()
        globals()["enable_discount_priority"] = var_discount.get()
        win.destroy()

    ttk.Button(frame, text="保存", command=save).pack(pady=5)

# ================================
# チュートリアル
# ================================
def open_tutorial_window():
    win = tk.Toplevel(root)
    win.title("チュートリアル")

    frame = ttk.Frame(win, padding=10)
    frame.pack(fill="both", expand=True)

    text_widget = tk.Text(frame, wrap="word", height=25, width=70)
    scrollbar = ttk.Scrollbar(frame, orient="vertical", command=text_widget.yview)
    text_widget.configure(yscrollcommand=scrollbar.set)

    text_widget.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")

    if not os.path.exists(TUTORIAL_FILE):
        text_widget.insert("1.0", "tutorial.txt が見つかりません。")
    else:
        with open(TUTORIAL_FILE, "r", encoding="utf-8") as f:
            text_widget.insert("1.0", f.read())

    text_widget.config(state="disabled")


# ================================
# アプリ終了時の処理
# ================================
def on_close():
    save_settings()
    root.destroy()


# ================================
# メイン画面
# ================================
root = tk.Tk()
root.title(f"ランダム兵団編成ツール v{VERSION}")
root.protocol("WM_DELETE_WINDOW", on_close)

main_frame = ttk.Frame(root, padding=15)
main_frame.pack(fill="both", expand=True)

# 統率値入力
ttk.Label(main_frame, text="統率値を入力:").pack(anchor="w")
entry = ttk.Entry(main_frame, width=20)
entry.pack(anchor="w", pady=5)

# 編成ボタン
ttk.Button(main_frame, text="編成する", command=on_generate).pack(pady=5)

# 設定ボタン群
btn_frame = ttk.Frame(main_frame)
btn_frame.pack(pady=10)

ttk.Button(
    btn_frame,
    text="所持兵団設定",
    command=lambda: open_checkbox_window("所持兵団設定", owned_units)
).grid(row=0, column=0, padx=5, pady=5)

ttk.Button(
    btn_frame,
    text="必須兵団設定",
    command=lambda: open_checkbox_window("必須兵団設定", required_units)
).grid(row=0, column=1, padx=5, pady=5)

ttk.Button(
    btn_frame,
    text="兵団ランク指定",
    command=open_star_required_window
).grid(row=1, column=0, padx=5, pady=5)

ttk.Button(
    btn_frame,
    text="統率軍魂有無設定",
    command=lambda: open_checkbox_window("統率軍魂有無設定", discount_units)
).grid(row=1, column=1, padx=5, pady=5)

ttk.Button(
    btn_frame,
    text="詳細オプション",
    command=open_final_adjust_window
).grid(row=2, column=0, padx=5, pady=5)

ttk.Button(
    btn_frame,
    text="チュートリアル",
    command=open_tutorial_window
).grid(row=2, column=1, padx=5, pady=5)

# 結果表示欄
text = tk.Text(main_frame, height=20, width=60)
text.pack()

root.mainloop()


