# python
import threading
import os
import io
import tkinter as tk
from tkinter import ttk, messagebox
from PIL import Image, ImageTk
import pyperclip

# 复用项目中的核心类与函数
from main_tui import ManosabaTextBox, draw_text_auto, paste_image_auto

class SimpleManosabaGUI:
    """
    极简 GUI：
    - 单一角色（取自 ManosabaTextBox 当前角色）
    - 文本输入框 + 从剪贴板粘贴图像预览
    - 生成按钮（后台线程），结果复制到剪贴板并可自动粘贴/发送
    """
    def __init__(self):
        self.textbox = ManosabaTextBox()
        # 强制只保留一个角色（当前）
        current = self.textbox.get_character()
        self.textbox.character_list = [current]
        self.textbox.current_character_index = 1

        self.root = tk.Tk()
        self.root.title("魔裁 - 简易生成器")
        self.root.geometry("640x480")

        self._build_ui()
        self.clip_image = None  # 存放从剪贴板获取的 PIL.Image

    def _build_ui(self):
        frm = ttk.Frame(self.root, padding=10)
        frm.pack(fill=tk.BOTH, expand=True)

        # 状态标签
        self.status_var = tk.StringVar(value="就绪")
        ttk.Label(frm, textvariable=self.status_var).pack(anchor=tk.W, pady=(0,8))

        # 文本输入
        ttk.Label(frm, text="要生成的文字（可不填）：").pack(anchor=tk.W)
        self.text_input = tk.Text(frm, height=6, wrap=tk.WORD)
        self.text_input.pack(fill=tk.BOTH, expand=False, pady=(0,8))

        # 图片预览区与按钮行
        preview_row = ttk.Frame(frm)
        preview_row.pack(fill=tk.X, pady=(0,8))

        self.preview_label = ttk.Label(preview_row, text="未检测到剪贴板图像", width=40, anchor=tk.CENTER)
        self.preview_label.pack(side=tk.LEFT, padx=(0,8))

        btn_col = ttk.Frame(preview_row)
        btn_col.pack(side=tk.LEFT, fill=tk.Y)

        ttk.Button(btn_col, text="从剪贴板读取图像", command=self.paste_image_from_clipboard).pack(fill=tk.X, pady=(0,4))
        ttk.Button(btn_col, text="清除预览", command=self.clear_preview).pack(fill=tk.X)

        # 选项：自动粘贴 / 自动发送
        opts = ttk.Frame(frm)
        opts.pack(fill=tk.X, pady=(0,8))
        self.auto_paste_var = tk.BooleanVar(value=self.textbox.AUTO_PASTE_IMAGE)
        self.auto_send_var = tk.BooleanVar(value=self.textbox.AUTO_SEND_IMAGE)
        ttk.Checkbutton(opts, text="自动粘贴到前台", variable=self.auto_paste_var, command=self._toggle_auto_paste).pack(side=tk.LEFT, padx=(0,8))
        ttk.Checkbutton(opts, text="自动按回车发送", variable=self.auto_send_var, command=self._toggle_auto_send).pack(side=tk.LEFT)

        # 操作按钮
        action_row = ttk.Frame(frm)
        action_row.pack(fill=tk.X, pady=(8,0))
        ttk.Button(action_row, text="生成图片", command=self.on_generate).pack(side=tk.LEFT, padx=(0,8))
        ttk.Button(action_row, text="退出", command=self.root.quit).pack(side=tk.LEFT)

        # 图片显示 canvas
        self.canvas = tk.Canvas(frm, bg="#222", height=200)
        self.canvas.pack(fill=tk.BOTH, expand=True, pady=(8,0))

    def _toggle_auto_paste(self):
        self.textbox.AUTO_PASTE_IMAGE = bool(self.auto_paste_var.get())
        if not self.auto_paste_var.get():
            # 若禁用自动粘贴，则自动发送也要禁用
            self.auto_send_var.set(False)
            self.textbox.AUTO_SEND_IMAGE = False

    def _toggle_auto_send(self):
        self.textbox.AUTO_SEND_IMAGE = bool(self.auto_send_var.get())

    def paste_image_from_clipboard(self):
        """尝试从 ManosabaTextBox.try_get_image 获取剪贴板图像并显示预览"""
        img = self.textbox.try_get_image()
        if img is None:
            messagebox.showinfo("信息", "剪贴板中未检测到图片。")
            return
        self.clip_image = img.copy()
        self._show_preview_image(self.clip_image)
        self.status_var.set("已读取剪贴板图像")

    def clear_preview(self):
        self.clip_image = None
        self.canvas.delete("all")
        self.preview_label.config(text="未检测到剪贴板图像")
        self.status_var.set("预览已清除")

    def _show_preview_image(self, pil_img):
        # 缩放适配 Canvas
        w, h = pil_img.size
        cw = self.canvas.winfo_width() or 600
        ch = self.canvas.winfo_height() or 200
        scale = min(cw / w, ch / h, 1.0)
        nw, nh = int(w * scale), int(h * scale)
        img_resized = pil_img.resize((nw, nh), Image.LANCZOS)
        self.tk_img = ImageTk.PhotoImage(img_resized)
        self.canvas.delete("all")
        self.canvas.create_image(cw//2, ch//2, image=self.tk_img, anchor=tk.CENTER)
        self.preview_label.config(text=f"剪贴板图像：{w}x{h}")

    def on_generate(self):
        """点击生成，后台线程执行生成逻辑"""
        threading.Thread(target=self._generate_worker, daemon=True).start()

    def _generate_worker(self):
        try:
            self.status_var.set("正在生成...")
            # 读取输入文本与剪贴板图像（优先使用 GUI 中的图像）
            text = self.text_input.get("1.0", tk.END).strip()
            image = self.clip_image

            character_name = self.textbox.get_character()
            # 生成随机基础图片路径（与原逻辑一致）
            baseimage_file = os.path.join(self.textbox.CACHE_PATH, self.textbox.get_random_value() + ".jpg")

            png_bytes = None

            if image is not None:
                # 使用 paste_image_auto 生成 PNG bytes
                png_bytes = paste_image_auto(
                    image_source=baseimage_file,
                    image_overlay=None,
                    top_left=(self.textbox.BOX_RECT[0][0], self.textbox.BOX_RECT[0][1]),
                    bottom_right=(self.textbox.BOX_RECT[1][0], self.textbox.BOX_RECT[1][1]),
                    content_image=image,
                    align="center",
                    valign="middle",
                    padding=12,
                    allow_upscale=True,
                    keep_alpha=True,
                    role_name=character_name,
                    text_configs_dict=self.textbox.text_configs_dict,
                )
            elif text:
                png_bytes = draw_text_auto(
                    image_source=baseimage_file,
                    image_overlay=None,
                    top_left=(self.textbox.BOX_RECT[0][0], self.textbox.BOX_RECT[0][1]),
                    bottom_right=(self.textbox.BOX_RECT[1][0], self.textbox.BOX_RECT[1][1]),
                    text=text,
                    align="left",
                    valign='top',
                    color=(255, 255, 255),
                    max_font_height=145,
                    font_path=self.textbox.get_current_font(),
                    role_name=character_name,
                    text_configs_dict=self.textbox.text_configs_dict,
                )
            else:
                self.status_var.set("错误：请输入文本或粘贴图片。")
                return

            if not png_bytes:
                self.status_var.set("生成失败：未获得图像字节。")
                return

            # 复制到剪贴板
            self.textbox.copy_png_bytes_to_clipboard(png_bytes)

            # 可选：在 GUI 中显示生成预览
            try:
                img = Image.open(io.BytesIO(png_bytes))
                self._show_preview_image(img)
            except Exception:
                pass

            # 自动粘贴/发送（如果启用）
            if self.textbox.AUTO_PASTE_IMAGE:
                # 模拟 Ctrl/Cmd+V
                kbd = self.textbox.kbd_controller
                from pynput.keyboard import Key
                ctrl_key = Key.ctrl if os.name != 'posix' else Key.cmd
                kbd.press(ctrl_key)
                kbd.press('v')
                kbd.release('v')
                kbd.release(ctrl_key)

                if self.textbox.AUTO_SEND_IMAGE:
                    kbd.press(Key.enter)
                    kbd.release(Key.enter)

            self.status_var.set("生成并复制到剪贴板，完成。")
        except Exception as e:
            self.status_var.set(f"生成失败: {e}")

    def run(self):
        self.root.mainloop()

if __name__ == "__main__":
    gui = SimpleManosabaGUI()
    gui.run()
