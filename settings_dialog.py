import tkinter as tk
from tkinter import ttk, messagebox
import threading
import os
import yaml
from sys import platform as _platform
import shutil
from tkinter import filedialog, colorchooser

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

        # 主容器 frame（必须先创建，后续 UI 都基于此）
        frm = ttk.Frame(self, padding=10)
        frm.pack(fill='both', expand=True)

        # 原有：self.var_hotkey / entry_hotkey / emote_hotkey_vars 替换为“按键记录”界面（标签 + 记录按钮）
        ttk.Label(frm, text="生成快捷键 (start_generate):").grid(row=0, column=0, sticky='w')
        self.hotkey_label_var = tk.StringVar(value=self.parent.textbox.keymap.get('start_generate', ''))
        lbl_hot = ttk.Label(frm, textvariable=self.hotkey_label_var, width=24, relief='sunken', anchor='w')
        lbl_hot.grid(row=0, column=1, padx=6, pady=4, sticky='w')
        # 将“记录”改为“绑定”
        btn_rec = ttk.Button(frm, text="绑定", width=8, command=lambda: self._start_recording('start_generate', lbl_hot))
        btn_rec.grid(row=0, column=2, padx=4, pady=4)
        # 为 start_generate 添加单独测试按钮
        btn_test_start = ttk.Button(frm, text="测试", width=6, command=lambda: self._on_test_key('start_generate'))
        btn_test_start.grid(row=0, column=3, padx=4, pady=4)

        # 切换表情 1~5：每行 显示标签 + 记录按钮（用更窄宽度以减小窗口宽度）
        self.emote_hotkey_labels = {}
        for i in range(1, 6):
            ttk.Label(frm, text=f"切换表情{i}:").grid(row=i, column=0, sticky='w')
            var = tk.StringVar(value=self.parent.textbox.keymap.get(f"switch_emote_{i}", ""))
            lbl = ttk.Label(frm, textvariable=var, width=24, relief='sunken', anchor='w')
            lbl.grid(row=i, column=1, padx=6, pady=2, sticky='w')
            # 将“记录”改为“绑定”
            btn = ttk.Button(frm, text="绑定", width=8, command=lambda n=i, w=lbl: self._start_recording(f"switch_emote_{n}", w))
            btn.grid(row=i, column=2, padx=4, pady=2)
            # 每行添加单独“测试”按钮
            btn_test = ttk.Button(frm, text="测试", width=6, command=lambda key=f"switch_emote_{i}": self._on_test_key(key))
            btn_test.grid(row=i, column=3, padx=4, pady=2)
            self.emote_hotkey_labels[i] = var

        # 记录状态内部字段
        self._recording_target = None       # key name like 'start_generate' or 'switch_emote_1'
        self._recording_widget = None       # widget 显示目标（Label）
        self._mod_keys = set()              # 当前按下的修饰键集合
        self._MODIFIER_KEYS = {'Shift_L','Shift_R','Control_L','Control_R','Alt_L','Alt_R','Meta_L','Meta_R','Super_L','Super_R','Win_L','Win_R'}
        # 每个绑定的临时测试句柄（keyname -> handle）
        self._test_handles = {}
        # 绑定按键事件（使用顶层绑定，grab_set 已经启用）
        self.bind("<KeyPress>", self._on_key_press)
        self.bind("<KeyRelease>", self._on_key_release)

        # 底部按钮区域：改为两行（便于放更多按钮且窗口更窄）
        btn_top = ttk.Frame(frm)
        btn_top.grid(row=7, column=0, columnspan=3, pady=(8,4), sticky='w')
        btn_bottom = ttk.Frame(frm)
        btn_bottom.grid(row=8, column=0, columnspan=3, pady=(0,8), sticky='e')

        btn_w = 10
        # 第一行：功能按钮
        self.btn_test = ttk.Button(btn_top, text="测试快捷键", command=self._on_test, width=btn_w)
        self.btn_test.pack(side='left', padx=6)
        self.btn_save = ttk.Button(btn_top, text="保存并注册", command=self._on_save, width=btn_w)
        self.btn_save.pack(side='left', padx=6)
        self.btn_clear_cache = ttk.Button(btn_top, text="清除缓存", command=self._on_delete_cache, width=btn_w)
        self.btn_clear_cache.pack(side='left', padx=6)
        self.btn_view_logs = ttk.Button(btn_top, text="查看日志", command=self._on_view_logs, width=btn_w)
        self.btn_view_logs.pack(side='left', padx=6)
        self.btn_manage_chars = ttk.Button(btn_top, text="管理角色", command=self._on_manage_characters, width=btn_w)
        self.btn_manage_chars.pack(side='left', padx=6)

        # 第二行：取消/关闭（靠右）
        self.btn_cancel = ttk.Button(btn_bottom, text="取消", command=self._on_cancel, width=12)
        self.btn_cancel.pack(side='right', padx=6)

        # 记录按键的临时句柄（用于测试快捷键时注册的全局热键）
        self._test_handle = None
        self._reload_after_close = False  # 新：标记是否在关闭后需要重载角色
        self.protocol("WM_DELETE_WINDOW", self._on_cancel)

    # 按键记录逻辑
    def _start_recording(self, target_keyname: str, widget):
        """开始记录按键组合，widget 为显示 Label"""
        # 若已有在记录，先取消
        try:
            if self._recording_target is not None:
                self._stop_recording()
            self._recording_target = target_keyname
            self._recording_widget = widget
            self._mod_keys.clear()
            # 提示用户（弹窗提醒已进入绑定模式）
            try:
                messagebox.showinfo("绑定", "已进入绑定模式：请按下想要绑定的组合键，或按 Esc 取消。", parent=self)
            except Exception:
                pass
            # 同时在标签上给出临时提示
            try:
                widget.config(text="绑定中... 按键或 Esc 取消")
            except Exception:
                pass
            # 确保窗口获得焦点以接收键盘事件
            try:
                self.focus_set()
            except Exception:
                pass
        except Exception:
            pass

    def _stop_recording(self):
        """停止记录（不修改已记录的值）"""
        try:
            # 不改变已保存的 label 内容，仅清理状态
            pass
        finally:
            self._recording_target = None
            self._recording_widget = None
            self._mod_keys.clear()

    def _on_key_press(self, event):
        if not self._recording_target:
            return
        ks = event.keysym
        # 收集修饰键
        if ks in self._MODIFIER_KEYS:
            self._mod_keys.add(ks)
            # 更新显示当前修饰键（不结束）
            try:
                mods = self._normalize_mods(self._mod_keys)
                if self._recording_widget:
                    self._recording_widget.config(text="+".join(mods) + "+...")
            except Exception:
                pass
            return
        # Esc 取消记录
        if ks == 'Escape':
            # 恢复显示为原值或空
            try:
                curval = self._get_current_label_var(self._recording_target)
                if self._recording_widget and curval is not None:
                    self._recording_widget.config(text=curval.get() if curval.get() else "")
                try:
                    messagebox.showinfo("已取消绑定", "绑定已取消。", parent=self)
                except Exception:
                    pass
            except Exception:
                pass
            self._stop_recording()
            return
        # 主键按下：组合完成，构造字符串并保存
        try:
            mods = self._normalize_mods(self._mod_keys)
            keyname = ks.upper() if len(ks) == 1 else ks
            combo = "+".join(mods + [keyname]) if mods else keyname
            # 写入对应变量（保存在 label 的 StringVar 中）
            var = self._get_current_label_var(self._recording_target)
            if var is not None:
                var.set(combo)
                # 更新显示 widget 文本
                try:
                    if self._recording_widget:
                        self._recording_widget.config(text=combo)
                except Exception:
                    pass
                # 绑定成功提醒
                try:
                    # 显示目标友好名称
                    target_display = self._recording_target
                    messagebox.showinfo("绑定成功", f"已将快捷键 [{combo}] 绑定到 [{target_display}]。", parent=self)
                except Exception:
                    pass
        except Exception:
            pass
        finally:
            self._stop_recording()

    def _on_key_release(self, event):
        # 释放修饰键时从集合中移除
        ks = event.keysym
        try:
            if ks in self._MODIFIER_KEYS and ks in self._mod_keys:
                self._mod_keys.discard(ks)
        except Exception:
            pass

    def _normalize_mods(self, mod_keys_set):
        """将修饰键集合归一化为标准名称顺序 ['Ctrl','Alt','Shift','Win']"""
        names = []
        s = set(mod_keys_set or ())
        if any(k.startswith('Control') or k.startswith('Ctrl') for k in s) or any('Control' in k for k in s):
            names.append('Ctrl')
        if any(k.startswith('Alt') for k in s):
            names.append('Alt')
        if any(k.startswith('Shift') for k in s):
            names.append('Shift')
        if any(k in ('Meta_L','Meta_R','Super_L','Super_R','Win_L','Win_R') for k in s):
            names.append('Win')
        return names

    def _get_current_label_var(self, keyname: str):
        if keyname == 'start_generate':
            return self.hotkey_label_var
        if keyname.startswith('switch_emote_'):
            try:
                n = int(keyname.split('_')[-1])
                return self.emote_hotkey_labels.get(n)
            except Exception:
                return None
        return None

    def _on_test(self):
        # 旧的全局测试方法保留为兼容（不再用于 UI）
        key = self.hotkey_label_var.get().strip()
        if not key:
            messagebox.showwarning("测试失败", "请先绑定一个快捷键后再测试。", parent=self)
            return
        messagebox.showinfo("测试说明", "请使用对应条目的“测试”按钮进行逐条测试。", parent=self)

    def _on_test_key(self, keyname: str):
        """为指定 keyname 注册一次性临时热键用于测试（仅 Windows 支持 keyboard 库）"""
        var = self._get_current_label_var(keyname)
        if var is None:
            messagebox.showwarning("测试失败", "无法获取要测试的绑定项。", parent=self)
            return
        key = var.get().strip()
        if not key:
            messagebox.showwarning("测试失败", "该绑定尚未设置，请先绑定。", parent=self)
            return
        if not PLATFORM.startswith('win'):
            messagebox.showinfo("测试说明", "当前平台不支持全局快捷键测试（仅在 Windows 使用 keyboard 库）。", parent=self)
            return
        try:
            import keyboard
        except Exception as e:
            messagebox.showerror("测试失败", f"无法导入 keyboard 库: {e}", parent=self)
            return
        # 移除已有该 key 的测试句柄
        try:
            old = self._test_handles.get(keyname)
            if old is not None:
                try:
                    keyboard.remove_hotkey(old)
                except Exception:
                    pass
                self._test_handles.pop(keyname, None)
        except Exception:
            pass

        def _on_trigger():
            try:
                # 在主线程显示提示
                self.after(0, lambda: messagebox.showinfo("快捷键测试", f"已捕获快捷键：{key}", parent=self))
            finally:
                # 自动注销该测试热键
                try:
                    keyboard.remove_hotkey(self._test_handles.get(keyname))
                except Exception:
                    pass
                try:
                    self._test_handles.pop(keyname, None)
                except Exception:
                    pass

        try:
            handle = keyboard.add_hotkey(key, _on_trigger)
            self._test_handles[keyname] = handle
            messagebox.showinfo("测试已就绪", f"请按下设定的快捷键 ({key}) 来触发测试弹窗。", parent=self)
        except Exception as e:
            messagebox.showerror("测试注册失败", f"注册测试快捷键失败: {e}", parent=self)

    def _on_save(self):
        new_key = self.hotkey_label_var.get().strip()
        # 更新内存映射
        if new_key:
            self.parent.textbox.keymap['start_generate'] = new_key
        else:
            # 删除映射（允许清空）
            if 'start_generate' in self.parent.textbox.keymap:
                del self.parent.textbox.keymap['start_generate']

        # 保存切换表情的快捷键配置（switch_emote_1..5）
        for i in range(1, 6):
            v = (self.emote_hotkey_labels.get(i).get() or "").strip()
            keyname = f"switch_emote_{i}"
            if v:
                self.parent.textbox.keymap[keyname] = v
            else:
                if keyname in self.parent.textbox.keymap:
                    del self.parent.textbox.keymap[keyname]

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
            # 统一注册所有 hotkey（_setup_global_hotkey 会读取 textbox.keymap）
            self.parent._setup_global_hotkey()
        except Exception as e:
            messagebox.showwarning("注册失败", f"保存成功但注册快捷键失败: {e}", parent=self)

        # 仍然关闭窗口
        self.destroy()

    def _on_cancel(self):
        # 停止记录监听（若在记录中）
        try:
            self._stop_recording()
        except Exception:
            pass
        # 清理测试句柄（如果存在）
        if self._test_handle is not None and PLATFORM.startswith('win'):
            try:
                import keyboard
                keyboard.remove_hotkey(self._test_handle)
            except Exception:
                pass
            self._test_handle = None

        # 如果之前执行了清除缓存，则在关闭设置窗口前触发主窗口重新加载上次选定的角色
        try:
            if getattr(self, "_reload_after_close", False):
                try:
                    # 优先通过 display -> id 映射获取角色 id
                    last_id = None
                    if hasattr(self.parent, "display_to_id"):
                        sel_display = getattr(self.parent, "char_var", None)
                        if sel_display:
                            # sel_display 可能是 StringVar
                            sel_val = sel_display.get() if hasattr(sel_display, "get") else sel_display
                            last_id = self.parent.display_to_id.get(sel_val)
                    # 兜底使用 textbox 提供的当前角色方法
                    if not last_id:
                        last_id = self.parent.textbox.get_character(None)
                    if last_id:
                        # 在主线程调用（load_character_images 本身会在后台线程执行加载）
                        try:
                            self.parent.load_character_images(last_id)
                        except Exception:
                            # 若直接调用失败，尝试放到主线程队列执行
                            try:
                                self.parent._call_in_main_thread(self.parent.load_character_images, last_id)
                            except Exception:
                                pass
                except Exception:
                    pass
        except Exception:
            pass

        self.destroy()

    def _on_delete_cache(self):
        try:
            self.parent.textbox.delete(self.parent.textbox.CACHE_PATH)
            # 标记：退出设置后需要重载上次选定角色
            self._reload_after_close = True
            # 通知主窗口状态（置为就绪）
            try:
                self.parent.update_status("缓存已清除，需要重新加载角色", state='ready')
            except Exception:
                pass
            messagebox.showinfo("清除完成", "缓存已清除。关闭设置后将自动重载上次选定的角色。", parent=self)
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

        # 居中（使用主窗口提供的 center_window，避免直接使用未稳定的 winfo_width/height）
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

        # 额外：从 text_configs.yml 中删除对应的名字配置（如果存在）
        try:
            txt_cfg_path = os.path.join(self.maingui.textbox.CONFIG_PATH, "text_configs.yml")
            try:
                with open(txt_cfg_path, 'r', encoding='utf-8') as ftxt:
                    tcfg = yaml.safe_load(ftxt) or {}
            except Exception:
                tcfg = {}
            if "text_configs" in tcfg and role in tcfg["text_configs"]:
                try:
                    del tcfg["text_configs"][role]
                    with open(txt_cfg_path, 'w', encoding='utf-8') as ftxt:
                        yaml.safe_dump(tcfg, ftxt, allow_unicode=True)
                except Exception:
                    pass
        except Exception:
            pass

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
        # 调整说明：角色专属背景 -> assets/background/chara/<id>；默认背景 -> assets/background/public
        menu.add_command(label="导入角色专属背景 (复制到 assets/background/chara/<id>)", command=lambda r=role: self._import_background(r))
        menu.add_command(label="导入默认背景 (复制到 assets/background/public)", command=lambda r=role: self._import_public_backgrounds(r))
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
        files = filedialog.askopenfilenames(title="选择要导入的角色专属背景图（多选）", filetypes=[("PNG", "*.png"),("JPG","*.jpg;*.jpeg"),("All","*.*")], parent=self)
        if not files:
            return
        # 导入到角色专属背景目录：assets/background/chara/<role_id>
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
        """将用户选择的背景复制到默认背景目录 assets/background/public（供所有角色回退使用）"""
        files = filedialog.askopenfilenames(title="选择要导入的默认背景图（多选）", filetypes=[("PNG", "*.png"),("JPG","*.jpg;*.jpeg"),("All","*.*")], parent=self)
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
        # 让第二列可扩展，避免控件被截断
        try:
            frm.columnconfigure(1, weight=1)
        except Exception:
            pass

        ttk.Label(frm, text="角色 ID (索引):").grid(row=0, column=0, sticky='w')
        self.var_id = tk.StringVar(value=role_id or "")
        ttk.Entry(frm, textvariable=self.var_id, width=30).grid(row=0, column=1, padx=6, pady=4, sticky='we')

        # 将标签名改为“角色名称”
        ttk.Label(frm, text="角色名称 (full_name):").grid(row=1, column=0, sticky='w')
        self.var_full = tk.StringVar()
        ttk.Entry(frm, textvariable=self.var_full, width=30).grid(row=1, column=1, padx=6, pady=4, sticky='we')

        ttk.Label(frm, text="字体文件名 (font):").grid(row=2, column=0, sticky='w')
        self.var_font = tk.StringVar()
        ttk.Entry(frm, textvariable=self.var_font, width=30).grid(row=2, column=1, padx=6, pady=4, sticky='we')

        ttk.Label(frm, text="表情数量 (emotion_count):").grid(row=3, column=0, sticky='w')
        self.var_emotion = tk.IntVar(value=1)
        ttk.Entry(frm, textvariable=self.var_emotion, width=10).grid(row=3, column=1, padx=6, pady=4, sticky='w')

        # 新增：字体颜色（R, G, B）允许用户自定义
        ttk.Label(frm, text="字体颜色 (R,G,B):").grid(row=4, column=0, sticky='w')
        # 将颜色输入与二级菜单包装在同一行
        color_wrap = ttk.Frame(frm)
        color_wrap.grid(row=4, column=1, padx=6, pady=4, sticky='w')

        color_frame = ttk.Frame(color_wrap)
        color_frame.pack(side='left')
        self.var_color_r = tk.IntVar(value=255)
        self.var_color_g = tk.IntVar(value=255)
        self.var_color_b = tk.IntVar(value=255)
        # 使用 Spinbox 让用户输入 0-255
        tk.Spinbox(color_frame, from_=0, to=255, width=4, textvariable=self.var_color_r).pack(side='left')
        tk.Label(color_frame, text=",").pack(side='left')
        tk.Spinbox(color_frame, from_=0, to=255, width=4, textvariable=self.var_color_g).pack(side='left')
        tk.Label(color_frame, text=",").pack(side='left')
        tk.Spinbox(color_frame, from_=0, to=255, width=4, textvariable=self.var_color_b).pack(side='left')

        # 二级菜单：颜色轮盘 + 预设色
        def set_color(r, g, b):
            try:
                self.var_color_r.set(int(max(0, min(255, r))))
                self.var_color_g.set(int(max(0, min(255, g))))
                self.var_color_b.set(int(max(0, min(255, b))))
            except Exception:
                pass

        def choose_color():
            try:
                res = colorchooser.askcolor(parent=self, title="选择颜色")
                if res and res[0]:
                    r, g, b = res[0]
                    set_color(r, g, b)
            except Exception:
                pass

        mb = tk.Menubutton(color_wrap, text="更多颜色 ▾", relief='raised')
        menu = tk.Menu(mb, tearoff=0)
        mb.config(menu=menu)
        menu.add_command(label="颜色轮盘...", command=choose_color)
        menu.add_separator()
        menu.add_command(label="预设：白", command=lambda: set_color(255, 255, 255))
        menu.add_command(label="预设：黑", command=lambda: set_color(0, 0, 0))
        menu.add_command(label="预设：红", command=lambda: set_color(235, 75, 60))
        menu.add_command(label="预设：绿", command=lambda: set_color(46, 204, 113))
        menu.add_command(label="预设：蓝", command=lambda: set_color(52, 152, 219))
        mb.pack(side='left', padx=(8,0))

        btn_frame = ttk.Frame(frm)
        btn_frame.grid(row=5, column=0, columnspan=2, pady=(8,0), sticky='e')
        ttk.Button(btn_frame, text="保存", command=self._on_save, width=10).pack(side='left', padx=6)
        ttk.Button(btn_frame, text="取消", command=self._on_cancel, width=10).pack(side='left', padx=6)

        # 如果 role_id 存在则预填充
        if role_id:
            try:
                cfg = self.maingui.textbox.mahoshojo.get(role_id, {})
                self.var_full.set(cfg.get("full_name", ""))
                self.var_font.set(cfg.get("font", ""))
                self.var_emotion.set(cfg.get("emotion_count", 1))
                # 尝试从 text_configs.yml 读取颜色预设
                try:
                    txt_cfg_path = os.path.join(self.maingui.textbox.CONFIG_PATH, "text_configs.yml")
                    with open(txt_cfg_path, 'r', encoding='utf-8') as ftxt:
                        tcfg = yaml.safe_load(ftxt) or {}
                        tc = tcfg.get("text_configs", {}).get(role_id)
                        if tc and isinstance(tc, list) and len(tc) > 0:
                            col = tc[0].get("font_color", [255,255,255])
                            if len(col) >= 3:
                                self.var_color_r.set(int(col[0]))
                                self.var_color_g.set(int(col[1]))
                                self.var_color_b.set(int(col[2]))
                except Exception:
                    pass
            except Exception:
                pass

        # 布局完成后再居中（使用主窗口提供的 center 方法，避免在控件尚未布局时计算错误）
        try:
            self.maingui.center_window(self)
        except Exception:
            try:
                self.update_idletasks()
                self.geometry(f"+{(self.winfo_screenwidth()-self.winfo_width())//2}+{(self.winfo_screenheight()-self.winfo_height())//2}")
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
        # 读取颜色
        try:
            cr = int(self.var_color_r.get()); cg = int(self.var_color_g.get()); cb = int(self.var_color_b.get())
            cr = max(0, min(255, cr)); cg = max(0, min(255, cg)); cb = max(0, min(255, cb))
        except Exception:
            cr, cg, cb = 255, 255, 255

        if not cid or em_cnt <= 0:
            messagebox.showwarning("输入错误", "请确保 ID 与 表情数量 有效。", parent=self)
            return

        # 若用户未填写显示名称，则使用 ID 作为显示名（避免“名字对话框内没有角色名字”）
        if not full:
            full = cid

        # 如果 font 是绝对路径或包含程序 assets 路径，保存时仅写文件名
        try:
            if font:
                if os.path.isabs(font):
                    font = os.path.basename(font)
                else:
                    # 若用户复制的是程序内绝对路径，也尝试提取 basename
                    if os.path.sep in font:
                        font = os.path.basename(font)
        except Exception:
            pass

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
            "font": font or os.path.basename(self.maingui.textbox.get_current_font()),
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

        # 额外：在 text_configs.yml 中为该角色创建名字配置模板（4 段），并保存用户选择的字体颜色
        try:
            txt_cfg_path = os.path.join(self.maingui.textbox.CONFIG_PATH, "text_configs.yml")
            try:
                with open(txt_cfg_path, 'r', encoding='utf-8') as ftxt:
                    tcfg = yaml.safe_load(ftxt) or {}
            except FileNotFoundError:
                tcfg = {}
            except Exception:
                tcfg = {}

            if "text_configs" not in tcfg or not isinstance(tcfg["text_configs"], dict):
                tcfg["text_configs"] = {}

            # 将 full 拆成至多 4 段（优先单字分段）
            segments = []
            s = full or ""
            for i in range(4):
                ch = s[i] if i < len(s) else ""
                segments.append(ch)

            # 默认位置与字号模板（可根据需要调整）
            default_positions = [[759,73], [943,110], [1093,175], [1183,175]]
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

            # 写回文件
            with open(txt_cfg_path, 'w', encoding='utf-8') as ftxt:
                yaml.safe_dump(tcfg, ftxt, allow_unicode=True)
        except Exception:
            # 非阻塞错误：不阻止保存成功
            pass

        try:
            self.maingui.textbox.load_configs()
            self.maingui._populate_characters()
        except Exception:
            pass

        messagebox.showinfo("保存成功", f"角色 {cid} 已保存。", parent=self)
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
