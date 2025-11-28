# python
# 文件: main_gui.py （第 1 部分：ManosabaTextBox）
import random
import time
import psutil
from pynput.keyboard import Key, Controller, GlobalHotKeys
import pyperclip
import io
from PIL import Image
import pyclip
from sys import platform
import os
import yaml
import tempfile
import subprocess
import threading

PLATFORM = platform.lower()

if PLATFORM.startswith('win'):
    try:
        import win32clipboard
        import keyboard
        import win32gui
        import win32process
    except ImportError:
        print("请先安装 Windows 运行库: pip install pywin32 keyboard")
        raise


class ManosabaTextBox:
    """主逻辑类（保持与原脚本逻辑一致）"""

    def __init__(self):
        # 常量定义
        self.BOX_RECT = ((728, 355), (2339, 800))  # 文本框区域坐标
        self.KEY_DELAY = 0.1  # 按键延迟
        self.AUTO_PASTE_IMAGE = True  # 自动粘贴图片
        self.AUTO_SEND_IMAGE = True  # 自动发送图片

        self.kbd_controller = Controller()  # 键盘控制器

        # 初始化路径
        self.BASE_PATH = ""  # 基础路径
        self.CONFIG_PATH = ""  # 配置路径
        self.ASSETS_PATH = ""  # 资源路径
        self.CACHE_PATH = ""  # 缓存路径
        self.setup_paths()

        # 加载配置
        self.mahoshojo = {}  # 角色元数据
        self.text_configs_dict = {}  # 文本配置字典
        self.character_list = []  # 角色列表
        self.keymap = {}  # 快捷键映射
        self.process_whitelist = []  # 进程白名单
        self.load_configs()

        # 状态变量
        self.emote = None  # 表情索引
        self.value_1 = -1  # 我也不知道这是啥我也不敢动
        self.current_character_index = 3  # 当前角色索引，默认第三个角色（sherri）

    def setup_paths(self):
        """设置文件路径"""
        self.BASE_PATH = os.path.dirname(os.path.abspath(__file__))
        self.CONFIG_PATH = os.path.join(self.BASE_PATH, "config")
        self.ASSETS_PATH = os.path.join(self.BASE_PATH, "assets")
        self.CACHE_PATH = os.path.join(self.ASSETS_PATH, "cache")
        os.makedirs(self.CACHE_PATH, exist_ok=True)

    def load_configs(self):
        """从yaml加载配置文件"""
        with open(os.path.join(self.CONFIG_PATH, "chara_meta.yml"), 'r', encoding="utf-8") as fp:
            config = yaml.safe_load(fp)
            self.mahoshojo = config["mahoshojo"]
            self.character_list = list(self.mahoshojo.keys())

        with open(os.path.join(self.CONFIG_PATH, "text_configs.yml"), 'r', encoding="utf-8") as fp:
            config = yaml.safe_load(fp)
            self.text_configs_dict = config["text_configs"]

        with open(os.path.join(self.CONFIG_PATH, "keymap.yml"), 'r', encoding="utf-8") as fp:
            config = yaml.safe_load(fp)
            self.keymap = config.get(PLATFORM, {})

        with open(os.path.join(self.CONFIG_PATH, "process_whitelist.yml"), 'r', encoding="utf-8") as fp:
            config = yaml.safe_load(fp)
            self.process_whitelist = config.get(PLATFORM, [])

    def get_character(self, index: str | None = None, full_name: bool = False) -> str:
        """
        获取角色名称
        Args:
            index: 角色索引名（不是序号，如果为None则返回当前角色）
            full_name: 是否返回全名
        Returns:
            角色名称 (str)
        """
        if index is not None:
            return self.mahoshojo[index]['full_name'] if full_name else index
        else:
            chara = self.character_list[self.current_character_index - 1]
            return self.mahoshojo[chara]['full_name'] if full_name else chara

    def switch_character(self, index: int) -> bool:
        """切换到指定索引的角色"""
        if 0 < index <= len(self.character_list):
            self.current_character_index = index
            return True
        return False

    def get_current_font(self) -> str:
        """返回当前角色的字体文件绝对路径"""
        return os.path.join(self.BASE_PATH, 'assets', 'fonts',
                            self.mahoshojo[self.get_character()]["font"])

    def get_current_emotion_count(self) -> int:
        """获取当前角色的表情数量"""
        return self.mahoshojo[self.get_character()]["emotion_count"]

    def delete(self, folder_path: str) -> None:
        """删除指定文件夹中的所有jpg文件"""
        for filename in os.listdir(folder_path):
            if filename.lower().endswith('.jpg'):
                os.remove(os.path.join(folder_path, filename))

    def generate_and_save_images(self, character_name: str, progress_callback=None) -> None:
        """生成并保存指定角色的所有表情图片"""
        emotion_cnt = self.mahoshojo[character_name]["emotion_count"]

        # 检查是否已经生成过
        for filename in os.listdir(self.CACHE_PATH):
            if filename.startswith(character_name):
                return

        total_images = 16 * emotion_cnt

        for j in range(emotion_cnt):
            for i in range(16):
                background_path = os.path.join(
                    self.BASE_PATH, 'assets', "background", f"c{i + 1}.png"
                )
                overlay_path = os.path.join(
                    self.BASE_PATH, 'assets', 'chara', character_name,
                    f"{character_name} ({j + 1}).png"
                )

                background = Image.open(background_path).convert("RGBA")
                overlay = Image.open(overlay_path).convert("RGBA")

                img_num = j * 16 + i + 1
                result = background.copy()
                result.paste(overlay, (0, 134), overlay)

                save_path = os.path.join(
                    self.CACHE_PATH, f"{character_name} ({img_num}).jpg"
                )
                result.convert("RGB").save(save_path)

                if progress_callback:
                    progress_callback(j * 16 + i + 1, total_images)

    def get_random_value(self) -> str:
        """随机获取表情图片名称"""
        character_name = self.get_character()
        emotion_cnt = self.get_current_emotion_count()
        total_images = 16 * emotion_cnt

        if self.emote:
            i = random.randint((self.emote - 1) * 16 + 1, self.emote * 16)
            self.value_1 = i
            self.emote = None
            return f"{character_name} ({i})"

        max_attempts = 100
        attempts = 0
        i = random.randint(1, total_images)

        while attempts < max_attempts:
            i = random.randint(1, total_images)
            current_emotion = (i - 1) // 16

            if self.value_1 == -1:
                self.value_1 = i
                return f"{character_name} ({i})"

            if current_emotion != (self.value_1 - 1) // 16:
                self.value_1 = i
                return f"{character_name} ({i})"

            attempts += 1

        self.value_1 = i
        return f"{character_name} ({i})"

    def copy_png_bytes_to_clipboard(self, png_bytes: bytes) -> None:
        """将PNG字节数据复制到剪贴板"""
        try:
            if PLATFORM == 'darwin':
                with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
                    tmp.write(png_bytes)
                    tmp_path = tmp.name

                cmd = f"""osascript -e 'set the clipboard to (read (POSIX file "{tmp_path}") as «class PNGf»)'"""
                result = subprocess.run(cmd, shell=True, capture_output=True)

                os.unlink(tmp_path)

                if result.returncode != 0:
                    print(f"复制图片到剪贴板失败: {result.stderr.decode()}")
            elif PLATFORM.startswith('win'):
                # 打开 PNG 字节为 Image
                image = Image.open(io.BytesIO(png_bytes))
                # 转换成 BMP 字节流（去掉 BMP 文件头的前 14 个字节）
                with io.BytesIO() as output:
                    image.convert("RGB").save(output, "BMP")
                    bmp_data = output.getvalue()[14:]
                # 打开剪贴板并写入 DIB 格式
                win32clipboard.OpenClipboard()
                win32clipboard.EmptyClipboard()
                win32clipboard.SetClipboardData(win32clipboard.CF_DIB, bmp_data)
                win32clipboard.CloseClipboard()
            else:
                # todo: Linux 支持
                pass
        except Exception as e:
            print(f"复制图片到剪贴板失败: {e}")

    def cut_all_and_get_text(self) -> str:
        """模拟全选和剪切操作，返回剪切得到的文本内容"""
        pyperclip.copy("")
        if PLATFORM == 'darwin':
            self.kbd_controller.press(Key.cmd)
            self.kbd_controller.press('a')
            self.kbd_controller.release('a')
            self.kbd_controller.press('x')
            self.kbd_controller.release('x')
            self.kbd_controller.release(Key.cmd)

        elif PLATFORM.startswith('win'):
            keyboard.send("CTRL+A")
            keyboard.send("CTRL+X")

        time.sleep(self.KEY_DELAY)
        new_clip = pyperclip.paste()
        return new_clip.strip()

    def try_get_image(self) -> Image.Image | None:
        """尝试从剪贴板获取图像"""
        if PLATFORM == 'darwin':
            try:
                data = pyclip.paste()

                if isinstance(data, bytes) and len(data) > 0:
                    try:
                        text = data.decode('utf-8')
                        if len(text) < 10000:
                            return None
                    except (UnicodeDecodeError, AttributeError):
                        pass

                    try:
                        image = Image.open(io.BytesIO(data))
                        image.load()
                        return image
                    except Exception:
                        return None

            except Exception as e:
                print(f"无法从剪贴板获取图像: {e}")
        elif PLATFORM.startswith('win'):
            try:
                win32clipboard.OpenClipboard()
                if win32clipboard.IsClipboardFormatAvailable(win32clipboard.CF_DIB):
                    data = win32clipboard.GetClipboardData(win32clipboard.CF_DIB)
                    if data:
                        # 将 DIB 数据转换为字节流，供 Pillow 打开
                        bmp_data = data
                        # DIB 格式缺少 BMP 文件头，需要手动加上
                        # BMP 文件头是 14 字节，包含 "BM" 标识和文件大小信息
                        header = b'BM' + (len(bmp_data) + 14).to_bytes(4,
                                                                       'little') + b'\x00\x00\x00\x00\x36\x00\x00\x00'
                        image = Image.open(io.BytesIO(header + bmp_data))
                        return image
            except Exception as e:
                print("无法从剪贴板获取图像：", e)
            finally:
                try:
                    win32clipboard.CloseClipboard()
                except:
                    pass
            return None
        else:
            # todo: Linux 支持
            return None

    def _active_process_allowed(self) -> bool:
        """校验当前前台进程是否在白名单"""
        if not self.process_whitelist:
            return True

        wl = {name.lower() for name in self.process_whitelist}

        if PLATFORM.startswith('win'):
            try:
                hwnd = win32gui.GetForegroundWindow()
                if not hwnd:
                    return False
                _, pid = win32process.GetWindowThreadProcessId(hwnd)
                name = psutil.Process(pid).name().lower()
                return name in wl
            except (psutil.Error, OSError):
                return False

        elif PLATFORM == 'darwin':
            try:
                result = subprocess.run(
                    ["osascript", "-e",
                     'tell application "System Events" to get name of first process whose frontmost is true'],
                    capture_output=True,
                    text=True,
                    check=True
                )
                name = result.stdout.strip().lower()
                return name in wl
            except subprocess.SubprocessError:
                return False

        else:
            # todo: Linux 支持
            return True

    def start(self) -> str:
        """生成并发送图片，返回状态消息"""
        if not self._active_process_allowed():
            return "前台应用不在白名单内"
        character_name = self.get_character()
        address = os.path.join(self.CACHE_PATH, self.get_random_value() + ".jpg")
        baseimage_file = address

        text_box_topleft = (self.BOX_RECT[0][0], self.BOX_RECT[0][1])
        image_box_bottomright = (self.BOX_RECT[1][0], self.BOX_RECT[1][1])
        text = self.cut_all_and_get_text()
        image = self.try_get_image()

        if text == "" and image is None:
            return "错误: 没有文本或图像"

        png_bytes = None

        if image is not None:
            try:
                from image_fit_paste import paste_image_auto
                png_bytes = paste_image_auto(
                    image_source=baseimage_file,
                    image_overlay=None,
                    top_left=text_box_topleft,
                    bottom_right=image_box_bottomright,
                    content_image=image,
                    align="center",
                    valign="middle",
                    padding=12,
                    allow_upscale=True,
                    keep_alpha=True,
                    role_name=character_name,
                    text_configs_dict=self.text_configs_dict,
                )
            except Exception as e:
                return f"生成图像失败: {e}"

        elif text is not None and text != "":
            try:
                from text_fit_draw import draw_text_auto
                png_bytes = draw_text_auto(
                    image_source=baseimage_file,
                    image_overlay=None,
                    top_left=text_box_topleft,
                    bottom_right=image_box_bottomright,
                    text=text,
                    align="left",
                    valign='top',
                    color=(255, 255, 255),
                    max_font_height=145,
                    font_path=self.get_current_font(),
                    role_name=character_name,
                    text_configs_dict=self.text_configs_dict,
                )

            except Exception as e:
                return f"生成图像失败: {e}"

        if png_bytes is None:
            return "生成图像失败！"

        self.copy_png_bytes_to_clipboard(png_bytes)

        if self.AUTO_PASTE_IMAGE:
            self.kbd_controller.press(Key.ctrl if PLATFORM != 'darwin' else Key.cmd)
            self.kbd_controller.press('v')
            self.kbd_controller.release('v')
            self.kbd_controller.release(Key.ctrl if PLATFORM != 'darwin' else Key.cmd)

            time.sleep(0.3)

            if self.AUTO_SEND_IMAGE:
                self.kbd_controller.press(Key.enter)
                self.kbd_controller.release(Key.enter)

        return f"成功生成图片！角色: {character_name}, 表情: {1 + (self.value_1 // 16)}"


# python
# 文件: main_gui.py （第 2 部分：GUI 窗口与启动入口）
import threading
import tkinter as tk
from tkinter import ttk, messagebox
from PIL import Image, ImageTk
import os
import sys
import time

# 假设 ManosabaTextBox 在同一文件中（如上），或者从 main_tui 导入：
# from main_tui import ManosabaTextBox
# 这里直接使用上面代码定义的 ManosabaTextBox

class ManosabaGUI:
    """Tkinter GUI 封装，保持原逻辑不变"""

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("魔裁 文本框生成器（GUI）")
        self.textbox = ManosabaTextBox()
        self.active = True
        self.hotkey_registered = False

        # UI 元素
        self.char_var = tk.StringVar()
        self.emotion_var = tk.IntVar(value=1)
        self.auto_paste_var = tk.BooleanVar(value=self.textbox.AUTO_PASTE_IMAGE)
        self.auto_send_var = tk.BooleanVar(value=self.textbox.AUTO_SEND_IMAGE)
        self.status_var = tk.StringVar(value="就绪")
        self.progress_var = tk.DoubleVar(value=0)

        self._build_ui()
        self._populate_characters()
        self._bind_events()

        # 预加载当前角色
        char_name = self.textbox.get_character(self.char_var.get() or None)
        self.load_character_images(char_name)

        # 尝试注册全局热键（可选）
        self._setup_global_hotkey()

    def open_settings(self):
        try:
            from settings_dialog import SettingsDialog
        except Exception as e:
            self.update_status(f"无法打开设置窗口: {e}")
            return
        SettingsDialog(self)

    def _register_global_hotkey(self, key: str):
        """注册全局热键（返回 handle 并保存到 self._hotkey_handle）"""
        if not PLATFORM.startswith('win'):
            self.update_status("仅 Windows 支持全局热键注册。")
            return
        try:
            import keyboard
        except Exception as e:
            self.update_status(f"无法导入 keyboard 库: {e}")
            return

        # 先移除已有句柄
        try:
            if getattr(self, '_hotkey_handle', None) is not None:
                keyboard.remove_hotkey(self._hotkey_handle)
                self._hotkey_handle = None
        except Exception:
            pass

        try:
            handle = keyboard.add_hotkey(key, lambda: self._call_in_main_thread(self.action_generate))
            self._hotkey_handle = handle
            self.hotkey_registered = True
            self.textbox.keymap['start_generate'] = key
            # 同步写回配置文件
            try:
                with open(os.path.join(self.textbox.CONFIG_PATH, "keymap.yml"), 'w', encoding='utf-8') as fp:
                    yaml.safe_dump({PLATFORM: self.textbox.keymap}, fp, allow_unicode=True)
            except Exception:
                pass
            self.update_status(f"已注册全局快捷键: {key}")
        except Exception as e:
            self.hotkey_registered = False
            self._hotkey_handle = None
            self.update_status(f"注册快捷键失败: {e}")

    def _unregister_global_hotkey(self):
        """移除已注册的全局热键（如果存在）"""
        if not PLATFORM.startswith('win'):
            return
        try:
            import keyboard
        except Exception:
            return
        try:
            if getattr(self, '_hotkey_handle', None) is not None:
                try:
                    keyboard.remove_hotkey(self._hotkey_handle)
                except Exception:
                    # 退回到清除所有热键的兜底方式
                    try:
                        keyboard.clear_all_hotkeys()
                    except Exception:
                        pass
                self._hotkey_handle = None
                self.hotkey_registered = False
                self.update_status("已取消全局快捷键。")
        except Exception:
            pass

    def _build_ui(self):
        frm = ttk.Frame(self.root, padding=8)
        frm.pack(fill='both', expand=True)

        # 顶部：角色选择、表情选择
        top = ttk.Frame(frm)
        top.pack(fill='x', pady=4)

        ttk.Label(top, text="角色:").grid(row=0, column=0, sticky='w')
        self.char_combo = ttk.Combobox(top, textvariable=self.char_var, state='readonly', width=40)
        self.char_combo.grid(row=0, column=1, padx=6, sticky='w')

        ttk.Label(top, text="表情:").grid(row=1, column=0, sticky='w')
        self.emotion_combo = ttk.Combobox(top, textvariable=self.emotion_var, state='readonly', width=10)
        self.emotion_combo.grid(row=1, column=1, padx=6, sticky='w')

        # 开关
        sw_frame = ttk.Frame(frm)
        sw_frame.pack(fill='x', pady=4)
        self.auto_paste_cb = ttk.Checkbutton(sw_frame, text="自动粘贴", variable=self.auto_paste_var, command=self._on_auto_paste_changed)
        self.auto_paste_cb.pack(side='left', padx=6)
        self.auto_send_cb = ttk.Checkbutton(sw_frame, text="自动发送", variable=self.auto_send_var, command=self._on_auto_send_changed)
        self.auto_send_cb.pack(side='left', padx=6)

        # 按钮
        btn_frame = ttk.Frame(frm)
        btn_frame.pack(fill='x', pady=6)
        self.btn_generate = ttk.Button(btn_frame, text="生成图片", command=self.action_generate)
        self.btn_generate.pack(side='left', padx=6)
        self.btn_delete_cache = ttk.Button(btn_frame, text="清除缓存", command=self.action_delete_cache)
        self.btn_delete_cache.pack(side='left', padx=6)
        self.btn_pause = ttk.Button(btn_frame, text="暂停/恢复", command=self.action_pause)
        self.btn_pause.pack(side='left', padx=6)
        self.btn_quit = ttk.Button(btn_frame, text="退出", command=self.action_quit)
        self.btn_quit.pack(side='right', padx=6)
        self.btn_settings = ttk.Button(btn_frame, text="设置", command=self.open_settings)
        self.btn_settings.pack(side='left', padx=6)

        # 进度与状态
        status_frame = ttk.Frame(frm)
        status_frame.pack(fill='x', pady=4)
        self.progress = ttk.Progressbar(status_frame, variable=self.progress_var, maximum=100)
        self.progress.pack(fill='x', padx=4, pady=2)
        self.status_label = ttk.Label(status_frame, textvariable=self.status_var)
        self.status_label.pack(anchor='w', padx=4)

    def _populate_characters(self):
        chars = self.textbox.character_list
        # 显示 id（索引名）供选择，但也可显示带全名
        self.char_combo['values'] = chars
        if chars:
            initial = self.textbox.get_character(None)
            self.char_var.set(initial)
            self._populate_emotions(initial)

    def _populate_emotions(self, char_id):
        try:
            # 获取情绪数量，填充表情下拉
            self.textbox.switch_character(self.textbox.character_list.index(char_id) + 1)
            cnt = self.textbox.get_current_emotion_count()
            values = list(range(1, cnt + 1))
            self.emotion_combo['values'] = values
            self.emotion_var.set(1)
            self.textbox.emote = 1
        except Exception:
            self.emotion_combo['values'] = []
            self.emotion_var.set(1)

    def _bind_events(self):
        self.char_combo.bind("<<ComboboxSelected>>", self._on_character_changed)
        self.emotion_combo.bind("<<ComboboxSelected>>", self._on_emotion_changed)
        self.root.protocol("WM_DELETE_WINDOW", self.action_quit)

    def _on_character_changed(self, event=None):
        selected = self.char_var.get()
        if selected:
            idx = self.textbox.character_list.index(selected) + 1
            self.textbox.switch_character(idx)
            # 后台加载
            self.load_character_images(selected)
            # 重置表情面板
            self._populate_emotions(selected)
            self.update_status(f"已选择角色: {selected}")

    def _on_emotion_changed(self, event=None):
        try:
            val = int(self.emotion_var.get())
            self.textbox.emote = val
            self.update_status(f"已选择表情 {val}")
        except Exception:
            pass

    def _on_auto_paste_changed(self):
        v = self.auto_paste_var.get()
        self.textbox.AUTO_PASTE_IMAGE = v
        if not v:
            self.textbox.AUTO_SEND_IMAGE = False
            self.auto_send_var.set(False)
            self.auto_send_cb.state(['disabled'])
        else:
            self.auto_send_cb.state(['!disabled'])
        self.update_status("自动粘贴已" + ("启用" if v else "禁用"))

    def _on_auto_send_changed(self):
        v = self.auto_send_var.get()
        self.textbox.AUTO_SEND_IMAGE = v
        self.update_status("自动发送已" + ("启用" if v else "禁用"))

    def _setup_global_hotkey(self):
        try:
            if PLATFORM.startswith('win'):
                km = self.textbox.keymap
                key = km.get('start_generate')
                if key:
                    self._register_global_hotkey(key)
        except Exception:
            self.hotkey_registered = False

    def _call_in_main_thread(self, func, *args, **kwargs):
        self.root.after(0, lambda: func(*args, **kwargs))

    def load_character_images(self, char_name: str):
        """后台加载角色图片并更新进度"""
        def update_progress(current, total):
            pct = int(current / total * 100) if total else 0
            self._call_in_main_thread(self._set_progress, pct)

        def worker():
            self._call_in_main_thread(self._set_ui_state, False)
            self._call_in_main_thread(self.update_status, f"正在加载角色 {self.textbox.get_character(char_name, full_name=True)} ...")
            try:
                self.textbox.generate_and_save_images(char_name, update_progress)
                self._call_in_main_thread(self.update_status, f"角色 {self.textbox.get_character(char_name, full_name=True)} 加载完成 ✓")
            except Exception as e:
                self._call_in_main_thread(self.update_status, f"加载失败: {e}")
            finally:
                self._call_in_main_thread(self._set_ui_state, True)
                self._call_in_main_thread(self._set_progress, 0)

        threading.Thread(target=worker, daemon=True).start()

    def _set_ui_state(self, enabled: bool):
        state = 'normal' if enabled else 'disabled'
        self.char_combo.config(state=state)
        self.emotion_combo.config(state=state)
        self.btn_generate.config(state=state)
        self.btn_delete_cache.config(state=state)
        self.btn_pause.config(state=state)

    def _set_progress(self, pct: int):
        self.progress_var.set(pct)

    def update_status(self, msg: str):
        self.status_var.set(str(msg))

    def action_generate(self):
        """在后台线程中调用 textbox.start 并更新状态"""
        if not self.active:
            self.update_status("已暂停，忽略生成请求")
            return

        def worker():
            self._call_in_main_thread(self._set_ui_state, False)
            self.update_status("正在生成图片...")
            try:
                result = self.textbox.start()
                self._call_in_main_thread(self.update_status, result)
            except Exception as e:
                self._call_in_main_thread(self.update_status, f"生成失败: {e}")
            finally:
                self._call_in_main_thread(self._set_ui_state, True)

        threading.Thread(target=worker, daemon=True).start()

    def action_delete_cache(self):
        self.update_status("正在清除缓存...")
        try:
            self.textbox.delete(self.textbox.CACHE_PATH)
            self.update_status("缓存已清除，需要重新加载角色")
        except Exception as e:
            self.update_status(f"清除缓存失败: {e}")

    def action_pause(self):
        self.active = not self.active
        status = "激活" if self.active else "暂停"
        self.update_status(f"应用已{status}。")
        self._set_ui_state(self.active)

    def action_quit(self):
        # 取消全局热键（如果注册）
        try:
            if self.hotkey_registered and PLATFORM.startswith('win'):
                import keyboard
                keyboard.clear_all_hotkeys()
        except Exception:
            pass
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = ManosabaGUI(root)
    root.mainloop()
