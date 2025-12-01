import tkinter as tk
from tkinter import ttk, messagebox
from tkinter import filedialog, colorchooser
import os
import yaml
import shutil
from sys import platform as _platform
import threading
import time
import webbrowser

PLATFORM = _platform.lower()


class SettingsDialog(tk.Toplevel):
    """设置窗口：快捷键绑定、导入/管理角色、查看日志等（语法已修复）"""

    def __init__(self, parent):
        try:
            super().__init__(parent.root)
            self.parent = parent  # ManosabaGUI 实例
            self.title("设置")
            self.transient(parent.root)
            self.resizable(False, False)
            self.grab_set()

            # 打开设置时先暂停主界面全局热键，避免抢占按键事件
            try:
                if hasattr(self.parent, "_unregister_global_hotkey"):
                    self.parent._unregister_global_hotkey()
            except Exception:
                pass

            frm = ttk.Frame(self, padding=10)
            frm.pack(fill='both', expand=True)

            # 生成快捷键
            ttk.Label(frm, text="生成快捷键:").grid(row=0, column=0, sticky='w')
            self.hotkey_var = tk.StringVar(value=self.parent.textbox.keymap.get('start_generate', ''))
            lbl_hot = ttk.Label(frm, textvariable=self.hotkey_var, width=28, relief='sunken', anchor='w')
            lbl_hot.grid(row=0, column=1, padx=6, pady=4, sticky='w')
            ttk.Button(frm, text="绑定", width=8, command=lambda: self._start_recording('start_generate')).grid(row=0, column=2, padx=4)
            ttk.Button(frm, text="测试", width=6, command=lambda: self._on_test_key('start_generate')).grid(row=0, column=3, padx=4)

            # 表情切换 1..5
            self.emote_vars = {}
            for i in range(1, 6):
                ttk.Label(frm, text=f"切换表情{i}:").grid(row=i, column=0, sticky='w')
                v = tk.StringVar(value=self.parent.textbox.keymap.get(f"switch_emote_{i}", ""))
                lbl = ttk.Label(frm, textvariable=v, width=28, relief='sunken', anchor='w')
                lbl.grid(row=i, column=1, padx=6, pady=2, sticky='w')
                ttk.Button(frm, text="绑定", width=8, command=lambda n=i: self._start_recording(f"switch_emote_{n}")).grid(row=i, column=2, padx=4)
                ttk.Button(frm, text="测试", width=6, command=lambda key=f"switch_emote_{i}": self._on_test_key(key)).grid(row=i, column=3, padx=4)
                self.emote_vars[i] = v

            # 新增：暂停生成 与 退出程序 的快捷键绑定（紧跟表情项）
            ttk.Label(frm, text="暂停生成:").grid(row=6, column=0, sticky='w')
            self.pause_var = tk.StringVar(value=self.parent.textbox.keymap.get('pause', self.parent.textbox.keymap.get('pause_app', '')))
            lbl_pause = ttk.Label(frm, textvariable=self.pause_var, width=28, relief='sunken', anchor='w')
            lbl_pause.grid(row=6, column=1, padx=6, pady=2, sticky='w')
            ttk.Button(frm, text="绑定", width=8, command=lambda: self._start_recording('pause')).grid(row=6, column=2, padx=4)
            ttk.Button(frm, text="测试", width=6, command=lambda: self._on_test_key('pause')).grid(row=6, column=3, padx=4)

            ttk.Label(frm, text="退出程序:").grid(row=7, column=0, sticky='w')
            self.quit_var = tk.StringVar(value=self.parent.textbox.keymap.get('quit', self.parent.textbox.keymap.get('quit_app', '')))
            lbl_quit = ttk.Label(frm, textvariable=self.quit_var, width=28, relief='sunken', anchor='w')
            lbl_quit.grid(row=7, column=1, padx=6, pady=2, sticky='w')
            ttk.Button(frm, text="绑定", width=8, command=lambda: self._start_recording('quit')).grid(row=7, column=2, padx=4)
            ttk.Button(frm, text="测试", width=6, command=lambda: self._on_test_key('quit')).grid(row=7, column=3, padx=4)

            # 记录与线程控制
            self._binding_thread = None
            self._binding_stop = threading.Event()

            # 底部按钮（功能：清除缓存 / 查看日志 / 管理角色 / 取消）
            top_btns = ttk.Frame(frm)
            top_btns.grid(row=8, column=0, columnspan=4, pady=(8, 4), sticky='w')
            bottom_btns = ttk.Frame(frm)
            bottom_btns.grid(row=9, column=0, columnspan=4, pady=(0, 8), sticky='e')

            ttk.Button(top_btns, text="清除缓存", command=self._on_delete_cache, width=12).pack(side='left', padx=6)
            ttk.Button(top_btns, text="查看日志", command=self._on_view_logs, width=12).pack(side='left', padx=6)
            ttk.Button(top_btns, text="管理角色", command=self._on_manage_characters, width=12).pack(side='left', padx=6)

            ttk.Button(bottom_btns, text="取消", command=self._on_cancel, width=12).pack(side='right', padx=6)
            # 新增：反馈问题 按钮（打开 GitHub issues 页面）
            ttk.Button(bottom_btns, text="反馈问题", command=self._on_report_issue, width=12).pack(side='right', padx=6)

            self.protocol("WM_DELETE_WINDOW", self._on_cancel)

            try:
                self.parent.center_window(self)
            except Exception:
                try:
                    self.update_idletasks()
                    self.geometry(f"+{(self.winfo_screenwidth()-self.winfo_width())//2}+{(self.winfo_screenheight()-self.winfo_height())//2}")
                except Exception:
                    pass

        except Exception as e:
            try:
                messagebox.showerror("设置窗口初始化失败", f"初始化失败: {e}", parent=parent.root)
            except Exception:
                print("设置窗口初始化失败:", e)
            try:
                self.destroy()
            except Exception:
                pass
            return

    # ---------- 绑定逻辑：优先使用 keyboard.read_hotkey（线程） ----------
    def _start_recording(self, keyname: str):
        """在后台线程等待一次全局热键并保存（需要 keyboard 库）"""
        # 先停止已有的线程（如果有）
        try:
            if self._binding_thread and self._binding_thread.is_alive():
                self._binding_stop.set()
                try:
                    self._binding_thread.join(timeout=0.1)
                except Exception:
                    pass
            self._binding_stop.clear()
        except Exception:
            pass

        # 暂停父窗口全局热键，避免冲突
        try:
            if hasattr(self.parent, "_unregister_global_hotkey"):
                self.parent._unregister_global_hotkey()
        except Exception:
            pass

        # 启动捕获线程
        def worker():
            combo = None
            used_keyboard = False
            try:
                try:
                    import keyboard
                    used_keyboard = True
                except Exception:
                    keyboard = None
                if keyboard is not None:
                    try:
                        # 阻塞直到下一次热键按下（返回形如 'ctrl+shift+a'）
                        hk = keyboard.read_hotkey(suppress=False)
                        combo = hk if hk else None
                    except Exception:
                        combo = None
                else:
                    # keyboard 不可用：提示用户并退出绑定线程
                    self._call_in_main_thread(messagebox.showwarning, "绑定受限", "缺少 keyboard 库，无法进行全局绑定。请安装 keyboard 库或使用系统支持方式。", {"parent": self})
                    return
            except Exception:
                combo = None
            finally:
                # 处理结果：在主线程应用绑定或提示取消
                def finish():
                    try:
                        if combo is None:
                            messagebox.showinfo("绑定取消", "未检测到按键或绑定被取消。", parent=self)
                        else:
                            # special-case esc as cancel
                            if str(combo).lower() in ('esc', 'escape'):
                                messagebox.showinfo("已取消绑定", "绑定已取消。", parent=self)
                            else:
                                # 保存并注册
                                self._apply_binding(keyname, combo)
                                # 弹窗显示友好项目名
                                proj_display = keyname
                                if keyname.startswith("switch_emote_"):
                                    try:
                                        n = int(keyname.split('_')[-1])
                                        proj_display = f"切换表情{n}"
                                    except Exception:
                                        proj_display = keyname
                                elif keyname == "start_generate":
                                    proj_display = "生成"
                                messagebox.showinfo("绑定成功", f"已将快捷键 [{combo}] 绑定到 [{proj_display}]。", parent=self)
                                # 绑定成功后：关闭设置窗口以退出绑定模式（但提示已弹出）
                                try:
                                    self.destroy()
                                except Exception:
                                    pass
                    except Exception:
                        pass
                    finally:
                        # 恢复父窗口热键（无论成功或取消）
                        try:
                            if hasattr(self.parent, "_setup_global_hotkey"):
                                self.parent._setup_global_hotkey()
                        except Exception:
                            pass

                try:
                    self._call_in_main_thread(finish)
                except Exception:
                    finish()

        try:
            self._binding_thread = threading.Thread(target=worker, daemon=True)
            self._binding_thread.start()
            messagebox.showinfo("提示", "已进入绑定模式：请在任意地方按下欲绑定的组合键。按 Esc 可取消。", parent=self)
        except Exception as e:
            try:
                messagebox.showerror("启动失败", f"无法启动绑定线程: {e}", parent=self)
            except Exception:
                pass
            # 尝试恢复父热键
            try:
                if hasattr(self.parent, "_setup_global_hotkey"):
                    self.parent._setup_global_hotkey()
            except Exception:
                pass

    def _apply_binding(self, keyname: str, combo: str):
        """将绑定写入 keymap.yml 并让主窗口重新注册热键（静默）"""
        try:
            if not hasattr(self.parent, "textbox"):
                return
            # 更新内存映射
            if combo:
                self.parent.textbox.keymap[keyname] = combo
            else:
                self.parent.textbox.keymap.pop(keyname, None)
            # 持久化到 keymap.yml
            cfg_path = os.path.join(self.parent.textbox.CONFIG_PATH, "keymap.yml")
            try:
                data = {PLATFORM: self.parent.textbox.keymap}
                with open(cfg_path, 'w', encoding='utf-8') as fp:
                    yaml.safe_dump(data, fp, allow_unicode=True)
            except Exception:
                pass
            # 重新注册全局热键（静默）
            try:
                if hasattr(self.parent, "_unregister_global_hotkey"):
                    self.parent._unregister_global_hotkey()
            except Exception:
                pass
            try:
                if hasattr(self.parent, "_setup_global_hotkey"):
                    self.parent._setup_global_hotkey()
            except Exception:
                pass
            # 同步更新界面上的显示变量（如果目标是 start_generate 或 switch_emote_n / pause / quit）
            try:
                if keyname == "start_generate":
                    self.hotkey_var.set(combo)
                elif keyname.startswith("switch_emote_"):
                    n = int(keyname.split("_")[-1])
                    if n in self.emote_vars:
                        self.emote_vars[n].set(combo)
                        # 绑定切换表情时，同时让主界面切换到该表情（在主线程执行）
                        try:
                            if hasattr(self.parent, "_call_in_main_thread"):
                                self.parent._call_in_main_thread(self.parent.action_switch_emote, n)
                            else:
                                self.parent.action_switch_emote(n)
                        except Exception:
                            # 兜底设置
                            try:
                                self.parent.textbox.emote = n
                                if hasattr(self.parent, "emotion_var"):
                                    try:
                                        self.parent._call_in_main_thread(self.parent.emotion_var.set, n)
                                    except Exception:
                                        self.parent.emotion_var.set(n)
                            except Exception:
                                pass
                elif keyname == 'pause':
                    try:
                        self.pause_var.set(combo)
                    except Exception:
                        pass
                elif keyname == 'quit':
                    try:
                        self.quit_var.set(combo)
                    except Exception:
                        pass
            except Exception:
                pass
        except Exception:
            pass

    def _on_test_key(self, keyname: str):
        """为指定绑定注册一次临时热键进行测试（仅在 Windows 且安装 keyboard 库时可用）"""
        var = None
        try:
            if keyname == 'start_generate':
                var = self.hotkey_var
            elif keyname.startswith('switch_emote_'):
                n = int(keyname.split('_')[-1])
                var = self.emote_vars.get(n)
        except Exception:
            var = None

        if var is None:
            messagebox.showwarning("测试失败", "绑定项不可用。", parent=self)
            return
        key = var.get().strip()
        if not key:
            messagebox.showwarning("测试失败", "该绑定尚未设置。", parent=self)
            return
        if not PLATFORM.startswith('win'):
            messagebox.showinfo("说明", "仅 Windows 平台支持全局热键测试（使用 keyboard 库）。", parent=self)
            return
        try:
            import keyboard
        except Exception as e:
            messagebox.showerror("测试失败", f"无法导入 keyboard 库: {e}", parent=self)
            return
        try:
            # 移除旧句柄（在当前会话内仅用于测试）
            handle = keyboard.add_hotkey(key, lambda: messagebox.showinfo("快捷键测试", f"已触发：{key}", parent=self))
            messagebox.showinfo("测试已就绪", f"请按下设定的快捷键 ({key}) 来触发测试弹窗。测试触发后自动取消。", parent=self)
            # 注册后在 10 秒内自动取消
            def remover():
                time.sleep(10)
                try:
                    keyboard.remove_hotkey(handle)
                except Exception:
                    pass
            threading.Thread(target=remover, daemon=True).start()
        except Exception as e:
            messagebox.showerror("测试失败", f"注册测试快捷键失败: {e}", parent=self)

    # ---------- 其它功能（清除缓存 / 查看日志 / 管理角色 / 导入） ----------
    def _on_delete_cache(self):
        try:
            self.parent.textbox.delete(self.parent.textbox.CACHE_PATH)
            self._reload_after_close = True
            try:
                self.parent.update_status("缓存已清除，需要重新加载角色", state='ready')
            except Exception:
                pass
            messagebox.showinfo("清除完成", "缓存已清除。关闭设置后将自动重载上次选定的角色。", parent=self)
        except Exception as e:
            messagebox.showerror("清除失败", f"清除缓存失败: {e}", parent=self)

    def _on_view_logs(self):
        try:
            self.parent.open_log_viewer(owner=self)
        except Exception as e:
            messagebox.showerror("查看日志失败", f"无法打开日志查看器: {e}", parent=self)

    def _on_manage_characters(self):
        try:
            CharacterListDialog(self, self.parent)
        except Exception as e:
            messagebox.showerror("打开失败", f"无法打开角色管理: {e}", parent=self)

    def _on_cancel(self):
        # 停止绑定线程并恢复父窗口热键
        try:
            self._binding_stop.set()
            try:
                if self._binding_thread and self._binding_thread.is_alive():
                    self._binding_thread.join(timeout=0.1)
            except Exception:
                pass
        except Exception:
            pass
        try:
            if hasattr(self.parent, "_setup_global_hotkey"):
                self.parent._setup_global_hotkey()
        except Exception:
            pass
        try:
            self.destroy()
        except Exception:
            pass

    def _on_report_issue(self):
        """在默认浏览器中打开项目 issue 页面用于反馈问题"""
        url = "https://github.com/mahiro76/manosaba_text_box/issues"
        try:
            webbrowser.open(url, new=2)  # new=2 尝试在新标签页打开
        except Exception as e:
            try:
                messagebox.showerror("打开失败", f"无法在浏览器中打开链接：{e}", parent=self)
            except Exception:
                pass


# 简化的角色管理与导入对话（保留现有行为）
class CharacterListDialog(tk.Toplevel):
    def __init__(self, parent, maingui):
        super().__init__(parent)
        self.parent = parent
        self.maingui = maingui
        self.title("角色管理")
        self.transient(parent)
        self.resizable(False, False)
        self.grab_set()

        frm = ttk.Frame(self, padding=10)
        frm.pack(fill='both', expand=True)

        left = ttk.Frame(frm)
        left.pack(side='left', fill='y', padx=(0, 8))

        ttk.Label(left, text="角色列表:").pack(anchor='w')
        self.lst = tk.Listbox(left, height=12, width=30)
        self.lst.pack(fill='y', expand=True)
        self._refresh_list()

        right = ttk.Frame(frm)
        right.pack(side='left', fill='both', expand=True)

        ttk.Label(right, text="操作:").pack(anchor='w')
        btn_frame = ttk.Frame(right)
        btn_frame.pack(anchor='n', pady=(6, 0))

        ttk.Button(btn_frame, text="新增", command=self._on_add, width=12).grid(row=0, column=0, padx=6, pady=4)
        ttk.Button(btn_frame, text="编辑", command=self._on_edit, width=12).grid(row=0, column=1, padx=6, pady=4)
        ttk.Button(btn_frame, text="删除", command=self._on_delete, width=12).grid(row=1, column=0, padx=6, pady=4)
        self.btn_import = ttk.Button(btn_frame, text="导入资源...", command=self._show_import_menu, width=26)
        self.btn_import.grid(row=1, column=1, padx=6, pady=4)
        ttk.Button(btn_frame, text="关闭", command=self.destroy, width=12).grid(row=2, column=0, columnspan=2, pady=(10, 0))

        try:
            self.maingui.center_window(self)
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

    def _selected_role(self):
        sel = self.lst.curselection()
        if not sel:
            return None
        idx = sel[0]
        try:
            return self.maingui.textbox.character_list[idx]
        except Exception:
            return None

    def _on_add(self):
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
        if not messagebox.askyesno("确认删除", f"确定要删除角色 {role} 吗？", parent=self):
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

        # 同步删除 text_configs 中的条目
        try:
            txt_cfg_path = os.path.join(self.maingui.textbox.CONFIG_PATH, "text_configs.yml")
            try:
                with open(txt_cfg_path, 'r', encoding='utf-8') as ftxt:
                    tcfg = yaml.safe_load(ftxt) or {}
            except Exception:
                tcfg = {}
            if "text_configs" in tcfg and role in tcfg["text_configs"]:
                del tcfg["text_configs"][role]
                try:
                    with open(txt_cfg_path, 'w', encoding='utf-8') as ftxt:
                        yaml.safe_dump(tcfg, ftxt, allow_unicode=True)
                except Exception:
                    pass
        except Exception:
            pass

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
        menu = tk.Menu(self, tearoff=0)
        menu.add_command(label="导入表情", command=lambda r=role: self._import_emotes_dialog(r))
        menu.add_command(label="导入角色背景 (assets/background/chara/<id>)", command=lambda r=role: self._import_background(r))
        menu.add_command(label="导入默认背景 (assets/background/public)", command=lambda r=role: self._import_public_backgrounds(r))
        menu.add_command(label="导入字体 (assets/fonts)", command=lambda r=role: self._import_fonts(r))
        try:
            menu.tk_popup(self.winfo_rootx() + self.btn_import.winfo_x(), self.winfo_rooty() + self.btn_import.winfo_y() + self.btn_import.winfo_height())
        finally:
            try:
                menu.grab_release()
            except Exception:
                pass

    def _import_emotes_dialog(self, role_id: str):
        try:
            em_cnt = int(self.maingui.textbox.mahoshojo.get(role_id, {}).get("emotion_count", 1))
        except Exception:
            em_cnt = 1
        dlg = ImportPerEmotionDialog(self, self.maingui, role_id, em_cnt)
        self.wait_window(dlg)
        try:
            self.maingui.textbox.load_configs()
            self._refresh_list()
        except Exception:
            pass

    def _import_background(self, role_id: str):
        files = filedialog.askopenfilenames(title="选择要导入的角色专属背景图（多选）", filetypes=[("图片", "*.png;*.jpg;*.jpeg;*.bmp"), ("All", "*.*")], parent=self)
        if not files:
            return
        try:
            dest_dir = os.path.join(self.maingui.textbox.ASSETS_PATH, 'background', 'chara', role_id)
            os.makedirs(dest_dir, exist_ok=True)
            copied = 0
            for f in files:
                try:
                    shutil.copy2(f, dest_dir)
                    copied += 1
                except Exception:
                    pass
            messagebox.showinfo("导入完成", f"已将 {copied} 个角色专属背景复制到 {dest_dir}", parent=self)
        except Exception as e:
            messagebox.showerror("导入失败", f"导入背景失败: {e}", parent=self)

    def _import_public_backgrounds(self, role_id: str):
        files = filedialog.askopenfilenames(title="选择要导入的默认背景图（多选）", filetypes=[("图片", "*.png;*.jpg;*.jpeg;*.bmp"), ("All", "*.*")], parent=self)
        if not files:
            return
        try:
            dest_dir = os.path.join(self.maingui.textbox.ASSETS_PATH, 'background', 'public')
            os.makedirs(dest_dir, exist_ok=True)
            copied = 0
            for f in files:
                try:
                    shutil.copy2(f, dest_dir)
                    copied += 1
                except Exception:
                    pass
            messagebox.showinfo("导入完成", f"已将 {copied} 个默认背景复制到 {dest_dir}", parent=self)
        except Exception as e:
            messagebox.showerror("导入失败", f"导入默认背景失败: {e}", parent=self)

    def _import_fonts(self, role_id: str):
        files = filedialog.askopenfilenames(title="选择要导入的字体文件（多选）", filetypes=[("字体", "*.ttf;*.otf"), ("All", "*.*")], parent=self)
        if not files:
            return
        try:
            dest_dir = os.path.join(self.maingui.textbox.ASSETS_PATH, 'fonts')
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
        try:
            frm.columnconfigure(1, weight=1)
        except Exception:
            pass

        ttk.Label(frm, text="角色 ID:").grid(row=0, column=0, sticky='w')
        self.var_id = tk.StringVar(value=role_id or "")
        ttk.Entry(frm, textvariable=self.var_id, width=30).grid(row=0, column=1, padx=6, pady=4, sticky='we')

        ttk.Label(frm, text="角色名称:").grid(row=1, column=0, sticky='w')
        self.var_full = tk.StringVar()
        ttk.Entry(frm, textvariable=self.var_full, width=30).grid(row=1, column=1, padx=6, pady=4, sticky='we')

        ttk.Label(frm, text="字体文件名:").grid(row=2, column=0, sticky='w')
        self.var_font = tk.StringVar()
        ttk.Entry(frm, textvariable=self.var_font, width=30).grid(row=2, column=1, padx=6, pady=4, sticky='we')

        ttk.Label(frm, text="表情数量:").grid(row=3, column=0, sticky='w')
        self.var_emotion = tk.IntVar(value=1)
        ttk.Entry(frm, textvariable=self.var_emotion, width=10).grid(row=3, column=1, padx=6, pady=4, sticky='w')

        ttk.Label(frm, text="字体颜色 (R,G,B):").grid(row=4, column=0, sticky='w')
        color_wrap = ttk.Frame(frm)
        color_wrap.grid(row=4, column=1, padx=6, pady=4, sticky='w')
        self.var_color_r = tk.IntVar(value=255)
        self.var_color_g = tk.IntVar(value=255)
        self.var_color_b = tk.IntVar(value=255)
        tk.Spinbox(color_wrap, from_=0, to=255, width=4, textvariable=self.var_color_r).pack(side='left')
        tk.Label(color_wrap, text=",").pack(side='left')
        tk.Spinbox(color_wrap, from_=0, to=255, width=4, textvariable=self.var_color_g).pack(side='left')
        tk.Label(color_wrap, text=",").pack(side='left')
        tk.Spinbox(color_wrap, from_=0, to=255, width=4, textvariable=self.var_color_b).pack(side='left')

        mb = tk.Menubutton(color_wrap, text="更多颜色 ▾", relief='raised')
        menu = tk.Menu(mb, tearoff=0)
        mb.config(menu=menu)
        menu.add_command(label="颜色轮盘...", command=lambda: self._choose_color())
        menu.add_separator()
        menu.add_command(label="白", command=lambda: self._set_color(255, 255, 255))
        menu.add_command(label="黑", command=lambda: self._set_color(0, 0, 0))
        mb.pack(side='left', padx=(8, 0))

        btns = ttk.Frame(frm)
        btns.grid(row=5, column=0, columnspan=2, pady=(8, 0), sticky='e')
        ttk.Button(btns, text="保存", command=self._on_save, width=10).pack(side='left', padx=6)
        ttk.Button(btns, text="取消", command=self._on_cancel, width=10).pack(side='left', padx=6)

        if role_id:
            try:
                cfg = self.maingui.textbox.mahoshojo.get(role_id, {})
                self.var_full.set(cfg.get("full_name", ""))
                self.var_font.set(cfg.get("font", ""))
                self.var_emotion.set(cfg.get("emotion_count", 1))
                try:
                    txt_cfg_path = os.path.join(self.maingui.textbox.CONFIG_PATH, "text_configs.yml")
                    with open(txt_cfg_path, 'r', encoding='utf-8') as ftxt:
                        tcfg = yaml.safe_load(ftxt) or {}
                        tc = tcfg.get("text_configs", {}).get(role_id)
                        if tc and isinstance(tc, list) and len(tc) > 0:
                            col = tc[0].get("font_color", [255, 255, 255])
                            if len(col) >= 3:
                                self.var_color_r.set(int(col[0])); self.var_color_g.set(int(col[1])); self.var_color_b.set(int(col[2]))
                except Exception:
                    pass
            except Exception:
                pass

        try:
            self.maingui.center_window(self)
        except Exception:
            try:
                self.update_idletasks()
                self.geometry(f"+{(self.winfo_screenwidth()-self.winfo_width())//2}+{(self.winfo_screenheight()-self.winfo_height())//2}")
            except Exception:
                pass

    def _choose_color(self):
        try:
            res = colorchooser.askcolor(parent=self, title="选择颜色")
            if res and res[0]:
                r, g, b = res[0]
                self._set_color(int(r), int(g), int(b))
        except Exception:
            pass

    def _set_color(self, r, g, b):
        try:
            self.var_color_r.set(max(0, min(255, int(r))))
            self.var_color_g.set(max(0, min(255, int(g))))
            self.var_color_b.set(max(0, min(255, int(b))))
        except Exception:
            pass

    def _on_save(self):
        cid = (self.var_id.get() or "").strip()
        full = (self.var_full.get() or "").strip()
        font = (self.var_font.get() or "").strip()
        try:
            em_cnt = int(self.var_emotion.get() or 1)
        except Exception:
            em_cnt = 1
        try:
            cr = int(self.var_color_r.get()); cg = int(self.var_color_g.get()); cb = int(self.var_color_b.get())
            cr = max(0, min(255, cr)); cg = max(0, min(255, cg)); cb = max(0, min(255, cb))
        except Exception:
            cr, cg, cb = 255, 255, 255

        if not cid or em_cnt <= 0:
            messagebox.showwarning("输入错误", "请确保 ID 与 表情数量 有效。", parent=self)
            return

        if not full:
            full = cid

        try:
            if font:
                font = os.path.basename(font)
        except Exception:
            pass

        cfg_file = os.path.join(self.maingui.textbox.CONFIG_PATH, "chara_meta.yml")
        try:
            try:
                with open(cfg_file, 'r', encoding='utf-8') as fp:
                    cfg = yaml.safe_load(fp) or {}
            except FileNotFoundError:
                cfg = {}
            if "mahoshojo" not in cfg:
                cfg["mahoshojo"] = {}
            cfg["mahoshojo"][cid] = {"full_name": full, "font": font or "", "emotion_count": em_cnt}
            with open(cfg_file, 'w', encoding='utf-8') as fp:
                yaml.safe_dump(cfg, fp, allow_unicode=True)
        except Exception as e:
            messagebox.showerror("保存失败", f"无法写入配置文件: {e}", parent=self)
            return

        # 更新 text_configs.yml 模板
        try:
            txt_cfg_path = os.path.join(self.maingui.textbox.CONFIG_PATH, "text_configs.yml")
            try:
                with open(txt_cfg_path, 'r', encoding='utf-8') as ftxt:
                    tcfg = yaml.safe_load(ftxt) or {}
            except FileNotFoundError:
                tcfg = {}
            if "text_configs" not in tcfg or not isinstance(tcfg["text_configs"], dict):
                tcfg["text_configs"] = {}
            segments = []
            s = full or ""
            for i in range(4):
                ch = s[i] if i < len(s) else ""
                segments.append(ch)
            default_positions = [[759, 73], [943, 110], [1093, 175], [1183, 175]]
            default_sizes = [186, 147, 92, 92]
            entries = []
            for idx in range(4):
                entries.append({
                    "text": segments[idx],
                    "position": default_positions[idx],
                    "font_color": [cr, cg, cb],
                    "font_size": default_sizes[idx]
                })
            tcfg["text_configs"][cid] = entries
            with open(txt_cfg_path, 'w', encoding='utf-8') as ftxt:
                yaml.safe_dump(tcfg, ftxt, allow_unicode=True)
        except Exception:
            pass

        try:
            self.maingui.textbox.load_configs()
            self.maingui._populate_characters()
        except Exception:
            pass

        messagebox.showinfo("保存成功", f"角色 {cid} 已保存。", parent=self)
        self.destroy()


class ImportPerEmotionDialog(tk.Toplevel):
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

        btns = ttk.Frame(frm)
        btns.pack(fill='x', pady=(8, 0))
        ttk.Button(btns, text="完成", command=self._on_done, width=12).pack(side='right')

        try:
            self.maingui.center_window(self)
        except Exception:
            pass

    def _import_single(self, idx: int, var: tk.StringVar):
        files = filedialog.askopenfilenames(title=f"选择用于 表情 {idx} 的图片", filetypes=[("图片", "*.png;*.jpg;*.jpeg;*.bmp"), ("All", "*.*")], parent=self)
        if not files:
            return
        src = files[0]
        try:
            dest_dir = os.path.join(self.maingui.textbox.ASSETS_PATH, 'chara', self.role_id)
            os.makedirs(dest_dir, exist_ok=True)
            basename = f"{self.role_id} ({idx}).png"
            dest_path = os.path.join(dest_dir, basename)
            try:
                shutil.copy2(src, dest_path)
            except Exception:
                try:
                    shutil.copy(src, dest_path)
                except Exception:
                    pass
            var.set(dest_path)
            messagebox.showinfo("导入完成", f"已复制到: {dest_path}", parent=self)
        except Exception as e:
            messagebox.showerror("导入失败", f"导入失败: {e}", parent=self)

    def _on_done(self):
        try:
            self.maingui.textbox.load_configs()
            try:
                self.parent._refresh_list()
            except Exception:
                pass
            self.maingui._populate_characters()
            self.maingui.update_status(f"角色 {self.role_id} 表情导入完成。", state='ready')
        except Exception:
            pass
        self.destroy()
