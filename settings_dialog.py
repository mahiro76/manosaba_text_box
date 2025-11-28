import tkinter as tk
from tkinter import ttk, messagebox
import threading
import os
import yaml
from sys import platform as _platform

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

        self.var_hotkey = tk.StringVar(value=self.parent.textbox.keymap.get('start_generate', ''))
        frm = ttk.Frame(self, padding=10)
        frm.pack(fill='both', expand=True)

        ttk.Label(frm, text="生成快捷键 (start_generate):").grid(row=0, column=0, sticky='w')
        self.entry_hotkey = ttk.Entry(frm, textvariable=self.var_hotkey, width=30)
        self.entry_hotkey.grid(row=0, column=1, padx=6, pady=4, sticky='w')

        btn_frame = ttk.Frame(frm)
        btn_frame.grid(row=1, column=0, columnspan=2, pady=(8,0), sticky='e')

        self.btn_test = ttk.Button(btn_frame, text="测试快捷键", command=self._on_test)
        self.btn_test.pack(side='left', padx=6)
        self.btn_save = ttk.Button(btn_frame, text="保存并注册", command=self._on_save)
        self.btn_save.pack(side='left', padx=6)
        self.btn_cancel = ttk.Button(btn_frame, text="取消", command=self._on_cancel)
        self.btn_cancel.pack(side='left', padx=6)

        self._test_handle = None
        self.protocol("WM_DELETE_WINDOW", self._on_cancel)

    def _on_test(self):
        key = self.var_hotkey.get().strip()
        if not key:
            messagebox.showwarning("测试失败", "请输入快捷键字符串（例如 Ctrl+Shift+G 或 ctrl+g 等）。")
            return

        # 注册临时回调来测试按键是否能触发（Windows 使用 keyboard）
        if PLATFORM.startswith('win'):
            try:
                import keyboard
            except Exception as e:
                messagebox.showerror("测试失败", f"无法导入 keyboard 库: {e}")
                return

            # 先移除上次测试句柄
            try:
                if self._test_handle is not None:
                    keyboard.remove_hotkey(self._test_handle)
            except Exception:
                pass

            def on_test_triggered():
                # 在主线程弹窗
                self.after(0, lambda: messagebox.showinfo("快捷键测试", f"已捕获快捷键：{key}"))
                # 测试一次后自动移除
                try:
                    keyboard.remove_hotkey(self._test_handle)
                except Exception:
                    pass
                self._test_handle = None

            try:
                self._test_handle = keyboard.add_hotkey(key, on_test_triggered)
                messagebox.showinfo("测试已就绪", f"请按下设定的快捷键 ({key}) 来触发测试弹窗。")
            except Exception as e:
                messagebox.showerror("测试注册失败", f"注册测试快捷键失败: {e}")
        else:
            messagebox.showinfo("测试说明", "当前平台不支持全局快捷键测试（本功能仅在 Windows 使用 keyboard 库）。")

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
            messagebox.showerror("保存失败", f"写入配置文件失败: {e}")
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
            messagebox.showwarning("注册失败", f"保存成功但注册快捷键失败: {e}")
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
