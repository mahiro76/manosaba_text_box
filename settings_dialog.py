import tkinter as tk
from tkinter import ttk, messagebox
import threading
import os
import yaml
from sys import platform as _platform
import shutil
from tkinter import filedialog

PLATFORM = _platform.lower()

class SettingsDialog(tk.Toplevel):
    """
    二级设置窗口：允许设置并测试 start_generate 全局快捷键。
    使用方法（在 main_gui 中调用）：
        from settings_dialog import SettingsDialog
        SettingsDialog(self)  # self 为 ManosabaGUI 实例
    """
    def __init__(self, parent):
        super().__init__(parent.root)
        self.parent = parent  # ManosabaGUI 实例
        self.title("设置")
        self.transient(parent.root)
        self.resizable(False, False)
        self.grab_set()

        # 居中设置窗口：仅设置位置，不强制修改宽高（确保控件已布局后再计算尺寸）
        try:
            self.update_idletasks()
            sw = self.winfo_screenwidth()
            sh = self.winfo_screenheight()
            w = self.winfo_width() or self.winfo_reqwidth()
            h = self.winfo_height() or self.winfo_reqheight()
            x = (sw - w) // 2
            y = (sh - h) // 2
            # 只设置位置，避免改变窗口自身计算的大小
            self.geometry(f"+{x}+{y}")
        except Exception:
            pass

        self.var_hotkey = tk.StringVar(value=self.parent.textbox.keymap.get('start_generate', ''))
        frm = ttk.Frame(self, padding=10)
        frm.pack(fill='both', expand=True)

        ttk.Label(frm, text="生成快捷键 (start_generate):").grid(row=0, column=0, sticky='w')
        self.entry_hotkey = ttk.Entry(frm, textvariable=self.var_hotkey, width=30)
        self.entry_hotkey.grid(row=0, column=1, padx=6, pady=4, sticky='w')

        btn_frame = ttk.Frame(frm)
        btn_frame.grid(row=1, column=0, columnspan=2, pady=(8,0), sticky='e')

        # 按钮改为更紧凑宽度
        btn_w = 10
        self.btn_test = ttk.Button(btn_frame, text="测试快捷键", command=self._on_test, width=btn_w)
        self.btn_test.pack(side='left', padx=6)
        self.btn_save = ttk.Button(btn_frame, text="保存并注册", command=self._on_save, width=btn_w)
        self.btn_save.pack(side='left', padx=6)

        # 新增：清除缓存按钮（从主界面移入设置）
        self.btn_clear_cache = ttk.Button(btn_frame, text="清除缓存", command=self._on_delete_cache, width=btn_w)
        self.btn_clear_cache.pack(side='left', padx=6)

        # 新增：查看日志按钮
        self.btn_view_logs = ttk.Button(btn_frame, text="查看日志", command=self._on_view_logs, width=btn_w)
        self.btn_view_logs.pack(side='left', padx=6)

        # 新增：管理角色按钮（弹出角色管理对话）
        self.btn_manage_chars = ttk.Button(btn_frame, text="管理角色", command=self._on_manage_characters, width=btn_w)
        self.btn_manage_chars.pack(side='left', padx=6)

        self.btn_cancel = ttk.Button(btn_frame, text="取消", command=self._on_cancel)
        self.btn_cancel.pack(side='left', padx=6)

        self._test_handle = None
        self.protocol("WM_DELETE_WINDOW", self._on_cancel)

    def _on_test(self):
        key = self.var_hotkey.get().strip()
        if not key:
            messagebox.showwarning("测试失败", "请输入快捷键字符串（例如 Ctrl+Shift+G 或 ctrl+g 等）。", parent=self)
            return

        # 注册临时回调来测试按键是否能触发（Windows 使用 keyboard）
        if PLATFORM.startswith('win'):
            try:
                import keyboard
            except Exception as e:
                messagebox.showerror("测试失败", f"无法导入 keyboard 库: {e}", parent=self)
                return

            # 先移除上次测试句柄
            try:
                if self._test_handle is not None:
                    keyboard.remove_hotkey(self._test_handle)
            except Exception:
                pass

            def on_test_triggered():
                # 在主线程弹窗
                self.after(0, lambda: messagebox.showinfo("快捷键测试", f"已捕获快捷键：{key}", parent=self))
                # 测试一次后自动移除
                try:
                    keyboard.remove_hotkey(self._test_handle)
                except Exception:
                    pass
                self._test_handle = None

            try:
                self._test_handle = keyboard.add_hotkey(key, on_test_triggered)
                messagebox.showinfo("测试已就绪", f"请按下设定的快捷键 ({key}) 来触发测试弹窗。", parent=self)
            except Exception as e:
                messagebox.showerror("测试注册失败", f"注册测试快捷键失败: {e}", parent=self)
        else:
            messagebox.showinfo("测试说明", "当前平台不支持全局快捷键测试（本功能仅在 Windows 使用 keyboard 库）。", parent=self)

    def _on_save(self):
        new_key = self.var_hotkey.get().strip()
        # 更新内存映射
        if new_key:
            self.parent.textbox.keymap['start_generate'] = new_key
        else:
            # 删除映射（允许清空）
            if 'start_generate' in self.parent.textbox.keymap:
                del self.parent.textbox.keymap['start_generate']

        # 写回配置文件 keymap.yml（保留 PLATFORM 键结构）
        cfg_path = os.path.join(self.parent.textbox.CONFIG_PATH, "keymap.yml")
        try:
            data = {PLATFORM: self.parent.textbox.keymap}
            with open(cfg_path, 'w', encoding='utf-8') as fp:
                yaml.safe_dump(data, fp, allow_unicode=True)
        except Exception as e:
            messagebox.showerror("保存失败", f"写入配置文件失败: {e}", parent=self)
            return

        # 在父窗口注册（或取消）全局热键
        try:
            # 先注销旧的
            self.parent._unregister_global_hotkey()
            if new_key:
                self.parent._register_global_hotkey(new_key)
            else:
                self.parent.update_status("已移除全局快捷键。")
        except Exception as e:
            messagebox.showwarning("注册失败", f"保存成功但注册快捷键失败: {e}", parent=self)
            # 仍然关闭窗口
        self.destroy()

    def _on_cancel(self):
        # 清理测试句柄（如果存在）
        if self._test_handle is not None and PLATFORM.startswith('win'):
            try:
                import keyboard
                keyboard.remove_hotkey(self._test_handle)
            except Exception:
                pass
            self._test_handle = None
        self.destroy()

    def _on_delete_cache(self):
        try:
            self.parent.textbox.delete(self.parent.textbox.CACHE_PATH)
            # 通知主窗口状态（置为就绪）
            try:
                self.parent.update_status("缓存已清除，需要重新加载角色", state='ready')
            except Exception:
                pass
            messagebox.showinfo("清除完成", "缓存已清除。", parent=self)
        except Exception as e:
            messagebox.showerror("清除失败", f"清除缓存失败: {e}", parent=self)

    def _on_view_logs(self):
        try:
            # 将当前设置窗口作为 owner 传入，使日志窗口能单独 grab 并关闭
            self.parent.open_log_viewer(owner=self)
        except Exception as e:
            messagebox.showerror("查看日志失败", f"无法打开日志查看器: {e}", parent=self)

    def _on_manage_characters(self):
        CharacterListDialog(self, self.parent)

# 替换原有的 CharacterManagerDialog 为列表界面与导入子界面
class CharacterListDialog(tk.Toplevel):
    """角色列表视图，支持删除与导入入口（导入为二级菜单）"""
    def __init__(self, parent, maingui):
        super().__init__(parent)
        self.parent = parent
        self.maingui = maingui  # ManosabaGUI 实例
        self.title("角色管理")
        self.transient(parent)
        self.resizable(False, False)
        self.grab_set()

        frm = ttk.Frame(self, padding=10)
        frm.pack(fill='both', expand=True)

        left = ttk.Frame(frm)
        left.pack(side='left', fill='y', padx=(0,8))

        ttk.Label(left, text="角色列表:").pack(anchor='w')
        self.lst = tk.Listbox(left, height=12, width=30)
        self.lst.pack(fill='y', expand=True)
        self._refresh_list()

        # 右侧动作面板
        right = ttk.Frame(frm)
        right.pack(side='left', fill='both', expand=True)

        ttk.Label(right, text="操作:").pack(anchor='w')
        btn_frame = ttk.Frame(right)
        btn_frame.pack(anchor='n', pady=(6,0))

        ttk.Button(btn_frame, text="新增", command=self._on_add, width=12).grid(row=0, column=0, padx=6, pady=4)
        ttk.Button(btn_frame, text="编辑", command=self._on_edit, width=12).grid(row=0, column=1, padx=6, pady=4)
        ttk.Button(btn_frame, text="删除", command=self._on_delete, width=12).grid(row=1, column=0, padx=6, pady=4)

        # 导入角色：提供弹出菜单（导入表情/背景/字体）
        self.btn_import = ttk.Button(btn_frame, text="导入角色 ▼", command=self._show_import_menu, width=26)
        self.btn_import.grid(row=1, column=1, padx=6, pady=4)

        ttk.Button(btn_frame, text="关闭", command=self.destroy, width=12).grid(row=2, column=0, columnspan=2, pady=(10,0))

        # 居中
        try:
            self.update_idletasks()
            self.master = parent
            self.geometry(f"+{(self.winfo_screenwidth()-self.winfo_width())//2}+{(self.winfo_screenheight()-self.winfo_height())//2}")
        except Exception:
            pass

    def _refresh_list(self):
        try:
            self.maingui.textbox.load_configs()
            self.lst.delete(0, 'end')
            for c in self.maingui.textbox.character_list:
                display = f"{c}  ({self.maingui.textbox.mahoshojo.get(c, {}).get('full_name','')})"
                self.lst.insert('end', display)
        except Exception:
            pass

    def _selected_role(self) -> str | None:
        sel = self.lst.curselection()
        if not sel:
            return None
        idx = sel[0]
        role_id = self.maingui.textbox.character_list[idx]
        return role_id

    def _on_add(self):
        # 复用原有保存逻辑：弹出简易新增对话
        dlg = _SimpleEditDialog(self, self.maingui)
        self.wait_window(dlg)
        self._refresh_list()

    def _on_edit(self):
        role = self._selected_role()
        if not role:
            messagebox.showwarning("未选择", "请先选择一个角色进行编辑。", parent=self)
            return
        dlg = _SimpleEditDialog(self, self.maingui, role_id=role)
        self.wait_window(dlg)
        self._refresh_list()

    def _on_delete(self):
        role = self._selected_role()
        if not role:
            messagebox.showwarning("未选择", "请先选择一个角色再删除。", parent=self)
            return
        if not messagebox.askyesno("确认删除", f"确定要删除角色 {role} 吗？此操作会从配置中移除该角色（不会自动删除资源文件）。", parent=self):
            return
        cfg_file = os.path.join(self.maingui.textbox.CONFIG_PATH, "chara_meta.yml")
        try:
            with open(cfg_file, 'r', encoding='utf-8') as fp:
                cfg = yaml.safe_load(fp) or {}
        except Exception as e:
            messagebox.showerror("读取失败", f"无法读取配置文件: {e}", parent=self)
            return
        try:
            if "mahoshojo" in cfg and role in cfg["mahoshojo"]:
                del cfg["mahoshojo"][role]
            with open(cfg_file, 'w', encoding='utf-8') as fp:
                yaml.safe_dump(cfg, fp, allow_unicode=True)
        except Exception as e:
            messagebox.showerror("删除失败", f"写入配置失败: {e}", parent=self)
            return
        # 重新加载并刷新
        try:
            self.maingui.textbox.load_configs()
            self._refresh_list()
            self.maingui._populate_characters()
            self.maingui.update_status(f"角色 {role} 已删除。", state='ready')
        except Exception:
            pass

    def _show_import_menu(self):
        role = self._selected_role()
        if not role:
            messagebox.showwarning("未选择", "请先选择一个角色再导入资源。", parent=self)
            return
        # 创建弹出菜单
        menu = tk.Menu(self, tearoff=0)
        menu.add_command(label="导入表情", command=lambda r=role: self._import_emotes_dialog(r))
        menu.add_command(label="导入背景 (复制到 assets/background)", command=lambda r=role: self._import_background(r))
        menu.add_command(label="导入字体 (复制到 assets/fonts)", command=lambda r=role: self._import_fonts(r))
        try:
            menu.tk_popup(self.winfo_rootx() + self.btn_import.winfo_x(), self.winfo_rooty() + self.btn_import.winfo_y() + self.btn_import.winfo_height())
        finally:
            menu.grab_release()

    def _import_emotes_dialog(self, role_id: str):
        # 弹出按表情数量动态生成的导入对话
        try:
            em_cnt = int(self.maingui.textbox.mahoshojo.get(role_id, {}).get("emotion_count", 1))
        except Exception:
            em_cnt = 1
        dlg = ImportPerEmotionDialog(self, self.maingui, role_id, em_cnt)
        self.wait_window(dlg)
        # 导入完后刷新
        try:
            self.maingui.textbox.load_configs()
            self._refresh_list()
        except Exception:
            pass

    def _import_background(self, role_id: str):
        files = filedialog.askopenfilenames(title="选择要导入的背景图（多选）", filetypes=[("PNG", "*.png"),("JPG","*.jpg;*.jpeg"),("All","*.*")], parent=self)
        if not files:
            return
        dest_dir = os.path.join(self.maingui.textbox.ASSETS_PATH, 'background')
        try:
            os.makedirs(dest_dir, exist_ok=True)
            copied = 0
            for f in files:
                try:
                    shutil.copy2(f, dest_dir)
                    copied += 1
                except Exception:
                    pass
            messagebox.showinfo("导入完成", f"已将 {copied} 个背景复制到 {dest_dir}", parent=self)
        except Exception as e:
            messagebox.showerror("导入失败", f"导入背景失败: {e}", parent=self)

    def _import_fonts(self, role_id: str):
        files = filedialog.askopenfilenames(title="选择要导入的字体文件（多选）", filetypes=[("字体", "*.ttf;*.otf"),("All","*.*")], parent=self)
        if not files:
            return
        dest_dir = os.path.join(self.maingui.textbox.ASSETS_PATH, 'fonts')
        try:
            os.makedirs(dest_dir, exist_ok=True)
            copied = 0
            for f in files:
                try:
                    shutil.copy2(f, dest_dir)
                    copied += 1
                except Exception:
                    pass
            messagebox.showinfo("导入完成", f"已将 {copied} 个字体复制到 {dest_dir}", parent=self)
        except Exception as e:
            messagebox.showerror("导入失败", f"导入字体失败: {e}", parent=self)


class _SimpleEditDialog(tk.Toplevel):
    """简化的新增/编辑对话，保留必要字段"""
    def __init__(self, parent, maingui, role_id: str | None = None):
        super().__init__(parent)
        self.parent = parent
        self.maingui = maingui
        self.title("新增/编辑角色")
        self.transient(parent)
        self.resizable(False, False)
        self.grab_set()

        frm = ttk.Frame(self, padding=10)
        frm.pack(fill='both', expand=True)

        ttk.Label(frm, text="角色 ID (索引):").grid(row=0, column=0, sticky='w')
        self.var_id = tk.StringVar(value=role_id or "")
        ttk.Entry(frm, textvariable=self.var_id, width=30).grid(row=0, column=1, padx=6, pady=4)

        ttk.Label(frm, text="显示名称 (full_name):").grid(row=1, column=0, sticky='w')
        self.var_full = tk.StringVar()
        ttk.Entry(frm, textvariable=self.var_full, width=30).grid(row=1, column=1, padx=6, pady=4)

        ttk.Label(frm, text="字体文件名 (font):").grid(row=2, column=0, sticky='w')
        self.var_font = tk.StringVar()
        ttk.Entry(frm, textvariable=self.var_font, width=30).grid(row=2, column=1, padx=6, pady=4)

        ttk.Label(frm, text="表情数量 (emotion_count):").grid(row=3, column=0, sticky='w')
        self.var_emotion = tk.IntVar(value=1)
        ttk.Entry(frm, textvariable=self.var_emotion, width=10).grid(row=3, column=1, padx=6, pady=4, sticky='w')

        btn_frame = ttk.Frame(frm)
        btn_frame.grid(row=4, column=0, columnspan=2, pady=(8,0), sticky='e')
        ttk.Button(btn_frame, text="保存", command=self._on_save, width=10).pack(side='left', padx=6)
        ttk.Button(btn_frame, text="取消", command=self._on_cancel, width=10).pack(side='left', padx=6)

        # 如果 role_id 存在则预填充
        if role_id:
            try:
                cfg = self.maingui.textbox.mahoshojo.get(role_id, {})
                self.var_full.set(cfg.get("full_name", ""))
                self.var_font.set(cfg.get("font", ""))
                self.var_emotion.set(cfg.get("emotion_count", 1))
            except Exception:
                pass

    def _on_save(self):
        cid = (self.var_id.get() or "").strip()
        full = (self.var_full.get() or "").strip()
        font = (self.var_font.get() or "").strip()
        try:
            em_cnt = int(self.var_emotion.get() or 0)
        except Exception:
            em_cnt = 1
        if not cid or not full or em_cnt <= 0:
            messagebox.showwarning("输入错误", "请确保 ID、显示名称 和 表情数量 有效。", parent=self)
            return

        cfg_file = os.path.join(self.maingui.textbox.CONFIG_PATH, "chara_meta.yml")
        try:
            with open(cfg_file, 'r', encoding='utf-8') as fp:
                cfg = yaml.safe_load(fp) or {}
        except FileNotFoundError:
            cfg = {}
        except Exception as e:
            messagebox.showerror("读取失败", f"无法读取配置文件: {e}", parent=self)
            return

        if "mahoshojo" not in cfg:
            cfg["mahoshojo"] = {}

        cfg["mahoshojo"][cid] = {
            "full_name": full,
            "font": font or self.maingui.textbox.get_current_font(),
            "emotion_count": em_cnt
        }

        try:
            with open(cfg_file, 'w', encoding='utf-8') as fp:
                yaml.safe_dump(cfg, fp, allow_unicode=True)
        except Exception as e:
            messagebox.showerror("保存失败", f"无法写入配置文件: {e}", parent=self)
            return

        try:
            char_dir = os.path.join(self.maingui.textbox.ASSETS_PATH, 'chara', cid)
            os.makedirs(char_dir, exist_ok=True)
        except Exception:
            pass

        try:
            self.maingui.textbox.load_configs()
            self.maingui._populate_characters()
        except Exception:
            pass

        messagebox.showinfo("保存成功", f"角色 {cid} 已保存。", parent=self)
        self.destroy()

    def _on_cancel(self):
        self.destroy()


class ImportPerEmotionDialog(tk.Toplevel):
    """根据角色 emotion_count 动态生成表情导入行（每行：标签、路径框、导入按钮）"""
    def __init__(self, parent, maingui, role_id: str, emotion_count: int):
        super().__init__(parent)
        self.parent = parent
        self.maingui = maingui
        self.role_id = role_id
        self.emotion_count = max(1, int(emotion_count or 1))
        self.title(f"为角色 {role_id} 导入表情 ({self.emotion_count})")
        self.transient(parent)
        self.resizable(False, False)
        self.grab_set()

        frm = ttk.Frame(self, padding=10)
        frm.pack(fill='both', expand=True)

        self.path_vars = []
        for i in range(1, self.emotion_count + 1):
            row = ttk.Frame(frm)
            row.pack(fill='x', pady=4)
            ttk.Label(row, text=f"表情 {i}:").pack(side='left')
            var = tk.StringVar()
            ent = ttk.Entry(row, textvariable=var, width=60)
            ent.pack(side='left', padx=6)
            btn = ttk.Button(row, text="导入", width=10, command=lambda idx=i, v=var: self._import_single(idx, v))
            btn.pack(side='left')
            self.path_vars.append(var)

        # 关闭按钮
        btns = ttk.Frame(frm)
        btns.pack(fill='x', pady=(8,0))
        ttk.Button(btns, text="完成", command=self._on_done, width=12).pack(side='right')

        # 居中
        try:
            self.update_idletasks()
            self.geometry(f"+{(self.winfo_screenwidth()-self.winfo_width())//2}+{(self.winfo_screenheight()-self.winfo_height())//2}")
        except Exception:
            pass

    def _import_single(self, idx: int, var: tk.StringVar):
        # 选择文件并复制到 assets/chara/<role_id>/<role_id> (idx).png
        files = filedialog.askopenfilenames(title=f"选择用于 表情 {idx} 的图片（可多选，会取第一项）", filetypes=[("图片", "*.png;*.jpg;*.jpeg;*.bmp"),("All","*.*")], parent=self)
        if not files:
            return
        src = files[0]
        try:
            dest_dir = os.path.join(self.maingui.textbox.ASSETS_PATH, 'chara', self.role_id)
            os.makedirs(dest_dir, exist_ok=True)
            # 目标文件名按程序现有格式命名
            basename = f"{self.role_id} ({idx}).png"
            dest_path = os.path.join(dest_dir, basename)
            shutil.copy2(src, dest_path)
            # 自动填写路径框（相对程序路径或绝对路径均可）
            var.set(dest_path)
            messagebox.showinfo("导入完成", f"已复制到: {dest_path}", parent=self)
        except Exception as e:
            messagebox.showerror("导入失败", f"导入失败: {e}", parent=self)

    def _on_done(self):
        # 导入完成后让主窗口重新加载资源（若需要）
        try:
            self.maingui.textbox.load_configs()
            self.parent._refresh_list()
            self.maingui._populate_characters()
            self.maingui.update_status(f"角色 {self.role_id} 表情导入完成。", state='ready')
        except Exception:
            pass
        self.destroy()
