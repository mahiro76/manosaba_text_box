# python
# 文件: main_gui.py （第 1 部分：ManosabaTextBox）
import io
import random
import time
# 可选依赖改为容错导入
try:
    import psutil
except Exception:
    psutil = None
try:
    from pynput.keyboard import Key, Controller, GlobalHotKeys
except Exception:
    # 提供最小 stub，避免未安装时导致导入失败
    class Key:
        ctrl = "ctrl"
        cmd = "cmd"
        enter = "enter"
    class Controller:
        def press(self, *a, **k): pass
        def release(self, *a, **k): pass
    GlobalHotKeys = None

# pyperclip / pyclip 容错
try:
    import pyperclip
except Exception:
    pyperclip = None
try:
    import pyclip
except Exception:
    pyclip = None

from sys import platform
import os
import yaml
import tempfile
import subprocess
import threading
import datetime
import glob

PLATFORM = platform.lower()

# Windows 特有库容错导入（不再 raise）
if PLATFORM.startswith('win'):
    try:
        import win32clipboard
    except Exception:
        win32clipboard = None
    try:
        import keyboard
    except Exception:
        keyboard = None
    try:
        import win32gui
    except Exception:
        win32gui = None
    try:
        import win32process
    except Exception:
        win32process = None


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
        """设置文件路径，兼容 PyInstaller onefile（使用 sys._MEIPASS）"""
        import sys
        # 如果运行在 PyInstaller onefile 模式，资源会被解到 sys._MEIPASS
        base = getattr(sys, "_MEIPASS", None)
        if base is None:
            base = os.path.dirname(os.path.abspath(__file__))
        self.BASE_PATH = base
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

        # 确保 current_character_index 在角色列表范围内（防止默认值超出）
        try:
            if not hasattr(self, "current_character_index") or self.current_character_index < 1:
                self.current_character_index = 1
            if self.character_list:
                # clamp 到 [1, len(character_list)]
                self.current_character_index = min(self.current_character_index, max(1, len(self.character_list)))
            else:
                # 若无角色，设为 1（后续 get_character 会处理空列表）
                self.current_character_index = 1
        except Exception:
            self.current_character_index = 1

    def get_character(self, index: str | None = None, full_name: bool = False) -> str:
        """
        获取角色名称
        Args:
            index: 角色索引名（不是序号，如果为None则返回当前角色）
            full_name: 是否返回全名
        Returns:
            角色名称 (str)
        """
        # 若传入具体索引名，直接返回（假设 caller 确认存在）
        if index is not None and index != "":
            try:
                return self.mahoshojo[index]['full_name'] if full_name else index
            except Exception:
                # 如果给定的 index 不存在，兜底返回空字符串
                return ""
        else:
            # 当没有角色时返回空字符串，调用者需做空值判断
            if not self.character_list:
                return ""
            # 确保 current_character_index 在合法范围内
            try:
                idx = max(0, min(self.current_character_index - 1, len(self.character_list) - 1))
                # 同步回 current_character_index（防止未来越界）
                self.current_character_index = idx + 1
                chara = self.character_list[idx]
                return self.mahoshojo[chara]['full_name'] if full_name else chara
            except Exception:
                return ""

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
        """生成并保存指定角色的所有表情图片（优先使用角色目录下的背景文件）"""
        emotion_cnt = self.mahoshojo[character_name]["emotion_count"]

        # 检查是否已经生成过
        for filename in os.listdir(self.CACHE_PATH):
            if filename.startswith(character_name):
                return

        total_images = 16 * emotion_cnt

        # 尝试获取角色专属背景文件列表（改为 assets/background/chara/<character>/*）
        # 旧路径： os.path.join(self.BASE_PATH, 'assets', 'chara', character_name, 'background')
        char_bg_dir = os.path.join(self.BASE_PATH, 'assets', 'background', 'chara', character_name)
        char_bg_files = []
        if os.path.isdir(char_bg_dir):
            for ext in ('*.png', '*.jpg', '*.jpeg', '*.bmp'):
                char_bg_files.extend(sorted(glob.glob(os.path.join(char_bg_dir, ext))))
            # 保持顺序且非空
            char_bg_files = [p for p in char_bg_files if os.path.isfile(p)]

        for j in range(emotion_cnt):
            for i in range(16):
                # 优先使用角色目录内背景（按序或循环），否则回退到全局 background/public/cN.png
                img_idx = j * 16 + i
                if char_bg_files:
                    bg_path = char_bg_files[img_idx % len(char_bg_files)]
                else:
                    # 改为使用 assets/background/public 作为默认背景目录
                    global_bg_path = os.path.join(self.BASE_PATH, 'assets', "background", "public", f"c{i + 1}.png")
                    bg_path = global_bg_path if os.path.isfile(global_bg_path) else None

                overlay_path = os.path.join(
                    self.BASE_PATH, 'assets', 'chara', character_name,
                    f"{character_name} ({j + 1}).png"
                )

                if bg_path is None or not os.path.isfile(overlay_path):
                    # 若任一资源缺失，跳过此张（避免异常导致全部失败）
                    continue

                try:
                    background = Image.open(bg_path).convert("RGBA")
                    overlay = Image.open(overlay_path).convert("RGBA")
                except Exception:
                    continue

                img_num = j * 16 + i + 1
                result = background.copy()
                # 固定粘贴位置（与原逻辑一致）
                result.paste(overlay, (0, 134), overlay)

                save_path = os.path.join(
                    self.CACHE_PATH, f"{character_name} ({img_num}).jpg"
                )
                try:
                    result.convert("RGB").save(save_path)
                except Exception:
                    # 忽略单张保存失败，继续生成剩余图片
                    pass

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
                if win32clipboard is None:
                    print("Warning: win32clipboard 未安装，无法复制图片到剪贴板")
                    return
                # 打开 PNG 字节为 Image
                image = Image.open(io.BytesIO(png_bytes))
                # 转换成 BMP 字节流（去掉 BMP 文件头的前 14 个字节）
                with io.BytesIO() as output:
                    image.convert("RGB").save(output, "BMP")
                    bmp_data = output.getvalue()[14:]
                # 打开剪贴板并写入 DIB 格式
                try:
                    win32clipboard.OpenClipboard()
                    win32clipboard.EmptyClipboard()
                    win32clipboard.SetClipboardData(win32clipboard.CF_DIB, bmp_data)
                finally:
                    try:
                        win32clipboard.CloseClipboard()
                    except Exception:
                        pass
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
        # 支持多个热键句柄（key -> handle）
        self._hotkey_handles = {}

        # 记录暂停时的角色 id，用于恢复后自动加载
        self.paused_char: str | None = None

        # UI 元素
        self.char_var = tk.StringVar()
        self.emotion_var = tk.IntVar(value=1)
        self.auto_paste_var = tk.BooleanVar(value=self.textbox.AUTO_PASTE_IMAGE)
        self.auto_send_var = tk.BooleanVar(value=self.textbox.AUTO_SEND_IMAGE)
        # 状态消息（进度旁显示的文本）
        self.status_msg_var = tk.StringVar(value="就绪")
        # 状态名字与颜色（单独显示的小条）
        self.status_state = 'ready'

        self.progress_var = tk.DoubleVar(value=0)

        # 日志相关
        self._log_lock = threading.Lock()
        self.log_dir = os.path.join(self.textbox.BASE_PATH, "log")
        os.makedirs(self.log_dir, exist_ok=True)
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        self.current_log_file = os.path.join(self.log_dir, f"startup_{ts}.log")
        # 轮换仅保留最近两次 startup_ 开头的日志
        try:
            existing = sorted(glob.glob(os.path.join(self.log_dir, "startup_*.log")))
            # append current immediately (file may not exist yet)
            existing.append(self.current_log_file)
            # keep only last 2
            to_keep = existing[-2:]
            for f in glob.glob(os.path.join(self.log_dir, "startup_*.log")):
                if f not in to_keep:
                    try:
                        os.remove(f)
                    except Exception:
                        pass
        except Exception:
            pass

        # 记录启动信息
        self._log("应用启动: " + datetime.datetime.now().isoformat())

        # 构建 UI
        self._build_ui()
        self._populate_characters()
        self._bind_events()

        # 将主窗口居中（使以 root 为 parent 的弹窗也以屏幕居中）
        self.center_window(self.root)

        # 预加载当前角色（仅在存在角色时）
        if self.textbox.character_list:
            current_id = self.textbox.get_character(None)
            if current_id:
                try:
                    self.load_character_images(current_id)
                except Exception:
                    # 如果加载失败也不要中断 GUI 启动
                    self.update_status("预加载角色失败，稍后请在设置中检查资源。", state='ready')
        else:
            # 没有读取到任何角色，提示用户去设置中添加
            try:
                self.update_status("未发现任何角色配置，请在设置中添加角色。", state='ready')
            except Exception:
                pass

        # 尝试注册全局热键（可选）
        self._setup_global_hotkey()

    def open_settings(self):
        try:
            from settings_dialog import SettingsDialog
        except Exception as e:
            self.update_status(f"无法打开设置窗口: {e}")
            return
        # 在打开设置窗口前暂停所有全局热键，避免它们抢占按键事件
        try:
            self._unregister_global_hotkey()
        except Exception:
            pass
        dlg = SettingsDialog(self)
        # 等待设置窗口关闭后再恢复全局热键（SettingsDialog 会在关闭时调用 parent._setup_global_hotkey 作二次保险）
        try:
            self.root.wait_window(dlg)
        except Exception:
            pass
        try:
            # 恢复注册（如果设置中有新的映射会生效）
            self._setup_global_hotkey()
        except Exception:
            pass

    def _register_global_hotkey(self, key: str, callback=None):
        """注册全局热键并返回 handle；callback 可选，默认触发生成"""
        if not PLATFORM.startswith('win'):
            self.update_status("仅 Windows 支持全局热键注册。")
            return None
        try:
            import keyboard
        except Exception as e:
            self.update_status(f"无法导入 keyboard 库: {e}")
            return None

        # 先移除已有相同 key 的句柄
        try:
            existing = self._hotkey_handles.get(key)
            if existing is not None:
                try:
                    keyboard.remove_hotkey(existing)
                except Exception:
                    pass
                del self._hotkey_handles[key]
        except Exception:
            pass

        try:
            if callback is None:
                cb = lambda: self._call_in_main_thread(self.action_generate)
            else:
                # wrap callback to ensure executed in main thread
                cb = lambda: self._call_in_main_thread(callback)

            handle = keyboard.add_hotkey(key, cb)
            # 记录句柄
            self._hotkey_handles[key] = handle
            self.hotkey_registered = True
            # 注册完成，写日志但不在状态栏重复显示
            try:
                self._log(f"已注册全局快捷键: {key}", level='info')
            except Exception:
                pass
            return handle
        except Exception as e:
            try:
                self._log(f"注册快捷键失败: {e}", level='warning')
            except Exception:
                pass
            return None

    def _unregister_global_hotkey(self):
        """移除已注册的全局热键（如果存在）"""
        if not PLATFORM.startswith('win'):
            return
        try:
            import keyboard
        except Exception:
            return
        try:
            for key, handle in list(self._hotkey_handles.items()):
                try:
                    if handle is not None:
                        keyboard.remove_hotkey(handle)
                except Exception:
                    pass
                try:
                    del self._hotkey_handles[key]
                except Exception:
                    pass
            self._hotkey_handles.clear()
            self.hotkey_registered = False
            try:
                self._log("已取消全局热键。", level='info')
            except Exception:
                pass
        except Exception:
            pass

    def _setup_global_hotkey(self):
        """根据 textbox.keymap 注册所有需要的全局热键（start_generate 与 switch_emote_*）"""
        try:
            if not PLATFORM.startswith('win'):
                return
            km = self.textbox.keymap
            # 先清理已有
            try:
                self._unregister_global_hotkey()
            except Exception:
                pass
            # 注册开始生成键（若存在）
            start_key = km.get('start_generate')
            if start_key:
                try:
                    self._register_global_hotkey(start_key, callback=lambda: self.action_generate())
                except Exception:
                    pass
            # 注册切换表情 1..5
            for n in range(1, 6):
                kname = f"switch_emote_{n}"
                key = km.get(kname)
                if key:
                    try:
                        # callback: 切换到第 n 表情
                        self._register_global_hotkey(key, callback=lambda n=n: self.action_switch_emote(n))
                    except Exception:
                        pass
        except Exception:
            pass

    def action_switch_emote(self, n: int):
        """通过快捷键切换到表情 n（1-based）"""
        try:
            n = int(n)
        except Exception:
            return
        # 设置内部状态与 UI
        try:
            # 若当前角色的 emotion_count 小于 n，则忽略
            cnt = 1
            try:
                cnt = self.textbox.get_current_emotion_count()
            except Exception:
                pass
            if n < 1 or n > max(1, cnt):
                self.update_status(f"表情 {n} 无效（当前角色表情数: {cnt}）", state='ready')
                return
            self.textbox.emote = n
            # 更新 UI 下拉框（主线程）
            try:
                self._call_in_main_thread(self.emotion_var.set, n)
            except Exception:
                self.emotion_var.set(n)
            self.update_status(f"已切换到表情 {n}")
        except Exception:
            pass

    def _build_ui(self):
        frm = ttk.Frame(self.root, padding=8)
        frm.pack(fill='both', expand=True)

        # 顶部：角色选择、表情选择
        top = ttk.Frame(frm)
        top.pack(fill='x', pady=4)

        ttk.Label(top, text="角色:").grid(row=0, column=0, sticky='w')
        # 改为显示“角色名称”（full_name）
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
        # 已移除：主界面清除缓存按钮（迁移至设置）
        # self.btn_delete_cache = ttk.Button(btn_frame, text="清除缓存", command=self.action_delete_cache)
        # self.btn_delete_cache.pack(side='left', padx=6)
        self.btn_pause = ttk.Button(btn_frame, text="暂停/恢复", command=self.action_pause)
        self.btn_pause.pack(side='left', padx=6)
        # 已移除：退出按钮
        # self.btn_quit = ttk.Button(btn_frame, text="退出", command=self.action_quit)
        # self.btn_quit.pack(side='right', padx=6)
        self.btn_settings = ttk.Button(btn_frame, text="设置", command=self.open_settings)
        self.btn_settings.pack(side='left', padx=6)

        # 进度与状态
        status_frame = ttk.Frame(frm)
        status_frame.pack(fill='x', pady=4)
        self.progress = ttk.Progressbar(status_frame, variable=self.progress_var, maximum=100)
        self.progress.pack(fill='x', padx=4, pady=2, side='left', expand=True)

        # 进度旁的提示信息（文本）
        self.status_msg_label = tk.Label(status_frame, textvariable=self.status_msg_var, anchor='w')
        self.status_msg_label.pack(side='left', padx=(6,4))

        # 状态显示（短条，带颜色与状态文字）
        self.state_label = tk.Label(status_frame, text="就绪", bd=1, relief='sunken', padx=6, pady=2)
        self.state_label.pack(side='right', padx=4)

        # 初始化状态颜色/文字
        self._apply_status_color('ready')

    def _populate_characters(self):
        # 使用 full_name 显示，但内部保留 id 映射
        chars = self.textbox.character_list  # list of ids
        display_names = []
        self.display_to_id = {}
        for cid in chars:
            try:
                full = str(self.textbox.mahoshojo.get(cid, {}).get('full_name', cid) or cid)
            except Exception:
                full = cid
            display_names.append(full)
            self.display_to_id[full] = cid
        self.char_combo['values'] = display_names
        if display_names:
            # 设定初始为当前角色的 full_name
            current_id = self.textbox.get_character(None)
            current_display = self.textbox.mahoshojo.get(current_id, {}).get('full_name', current_id)
            self.char_var.set(current_display)
            # 填充表情，传入 id
            self._populate_emotions(current_id)

    def _populate_emotions(self, char_id):
        try:
            # char_id 是 id（索引名）
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
        selected_display = self.char_var.get()
        if not selected_display:
            return
        # 把显示名映射回 id
        cid = self.display_to_id.get(selected_display)
        if not cid:
            # 兜底（若用户编辑或配置异常），尝试按 id 匹配
            if selected_display in self.textbox.character_list:
                cid = selected_display
        if not cid:
            self.update_status("选择的角色无效", state='ready')
            return
        idx = self.textbox.character_list.index(cid) + 1
        self.textbox.switch_character(idx)
        # 后台加载（传入 id）
        self.load_character_images(cid)
        # 重置表情面板
        self._populate_emotions(cid)
        self.update_status(f"已选择角色: {selected_display}")

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
        """后台加载角色图片并更新进度
           char_name 这里是角色 id（索引名）
        """
        def update_progress(current, total):
            pct = int(current / total * 100) if total else 0
            self._call_in_main_thread(self._set_progress, pct)

        def worker():
            # 在开始时明确进入“生成中/加载中”状态（确保颜色为黄）
            self._call_in_main_thread(self._set_ui_state, False)
            self._call_in_main_thread(self.update_status, f"正在加载角色 {self.textbox.get_character(char_name, full_name=True)} ...", 'running')
            try:
                # 修改：generate_and_save_images 将优先使用角色目录下的背景
                self.textbox.generate_and_save_images(char_name, update_progress)
                # 加载完成后明确恢复为就绪（绿色）
                self._call_in_main_thread(self.update_status, f"角色 {self.textbox.get_character(char_name, full_name=True)} 加载完成 ✓", 'ready')
            except Exception as e:
                # 失败也切回就绪，显示错误信息
                self._call_in_main_thread(self.update_status, f"加载失败: {e}", 'ready')
            finally:
                self._call_in_main_thread(self._set_ui_state, True)
                self._call_in_main_thread(self._set_progress, 0)

        threading.Thread(target=worker, daemon=True).start()

    def _set_ui_state(self, enabled: bool):
        state = 'normal' if enabled else 'disabled'
        self.char_combo.config(state=state)
        self.emotion_combo.config(state=state)
        self.btn_generate.config(state=state)
        # 注意：不要禁用暂停按钮，否则无法恢复
        # self.btn_pause.config(state=state)  # 已移除

    def _set_progress(self, val: float):
        """主线程调用：设置进度（0-100），容错并限制范围。"""
        try:
            v = float(val or 0)
        except Exception:
            v = 0.0
        if v < 0:
            v = 0.0
        if v > 100:
            v = 100.0
        try:
            self.progress_var.set(v)
            # 立即刷新 UI（在主线程）
            try:
                self.progress.update_idletasks()
            except Exception:
                pass
        except Exception:
            pass

    # 新：内部方法，根据状态设置颜色和状态短条文本
    def _apply_status_color(self, state: str):
        # 三种颜色：就绪(绿), 生成中(黄), 已暂停(红)
        mapping = {
            'ready': ('就绪', '#2ecc71'),      # 绿
            'running': ('生成中', '#f1c40f'),  # 黄
            'paused': ('已暂停', '#e74c3c'),   # 红
        }
        text, color = mapping.get(state, ('就绪', '#2ecc71'))
        self.status_state = state
        # 设置短条文本与颜色（state_label）
        try:
            self.state_label.config(text=text, bg=color, fg='black')
        except Exception:
            pass
        # 如果没有额外消息时，保持进度旁消息与状态短条一致
        try:
            if not self.status_msg_var.get() or self.status_msg_var.get() in ('就绪', '生成中...', '应用已暂停。', '应用已激活。'):
                self.status_msg_var.set(text)
        except Exception:
            pass

    def update_status(self, msg: str = None, state: str | None = None):
        if state:
            # 先更新颜色/短条
            self._apply_status_color(state)
        if msg is not None:
            # 将提示文本显示在进度旁
            try:
                self.status_msg_var.set(str(msg))
            except Exception:
                pass
            # 记录日志
            try:
                self._log(str(msg))
            except Exception:
                pass

    # 新：打开日志查看器（显示最近两次启动日志内容）
    def open_log_viewer(self, owner: tk.Toplevel | tk.Tk | None = None):
        try:
            from tkinter.scrolledtext import ScrolledText
        except Exception:
            ScrolledText = None

        parent_win = owner if owner is not None else self.root
        win = tk.Toplevel(parent_win)
        win.title("查看日志")
        win.transient(parent_win)
        win.resizable(True, True)

        # 日志等级选择（All / info / warning / error）
        top_frame = ttk.Frame(win, padding=6)
        top_frame.pack(fill='x')
        ttk.Label(top_frame, text="日志等级:").pack(side='left')
        lvl_var = tk.StringVar(value="all")
        lvl_menu = ttk.Combobox(top_frame, textvariable=lvl_var, values=["all", "info", "warning", "error"], state='readonly', width=8)
        lvl_menu.pack(side='left', padx=(6,8))

        btn_refresh = ttk.Button(top_frame, text="刷新", width=8, command=lambda: _load_logs())
        btn_refresh.pack(side='left', padx=4)
        btn_close = ttk.Button(top_frame, text="关闭", width=8, command=win.destroy)
        btn_close.pack(side='right', padx=4)

        if ScrolledText is None:
            lbl = tk.Label(win, text="无法加载 ScrolledText，查看日志文件目录：" + self.log_dir)
            lbl.pack(fill='both', expand=True, padx=8, pady=8)
        else:
            st = ScrolledText(win, wrap='none', width=100, height=30)
            st.pack(fill='both', expand=True, padx=6, pady=(0,6))
            st.configure(state='disabled')

            def _load_logs():
                try:
                    st.configure(state='normal')
                    st.delete('1.0', 'end')
                    files = sorted(glob.glob(os.path.join(self.log_dir, "startup_*.log")))
                    last_two = files[-2:] if files else []
                    level_filter = lvl_var.get().lower()
                    for f in last_two:
                        st.insert('end', f"===== {os.path.basename(f)} =====\n")
                        try:
                            with open(f, 'r', encoding='utf-8') as fp:
                                for line in fp:
                                    if level_filter == "all":
                                        st.insert('end', line)
                                    else:
                                        # 只显示包含对应 [level] 的行
                                        if f"[{level_filter}]" in line.lower():
                                            st.insert('end', line)
                        except Exception:
                            st.insert('end', f"(无法读取 {f})\n")
                    st.see('end')
                except Exception as e:
                    try:
                        st.insert('end', f"读取日志失败: {e}")
                    except Exception:
                        pass
                finally:
                    try:
                        st.configure(state='disabled')
                    except Exception:
                        pass

            _load_logs()

        # 居中并设置 grab，这样即使 settings 有 grab 也能在日志窗口操作并关闭
        try:
            self.center_window(win)
            win.grab_set()
        except Exception:
            pass

    def action_generate(self):
        """在后台线程中调用 textbox.start 并更新状态"""
        if not self.active:
            self.update_status("已暂停，忽略生成请求", state='paused')
            return

        def worker():
            self._call_in_main_thread(self._set_ui_state, False)
            # 标记生成中状态
            self._call_in_main_thread(self.update_status, "生成中...", 'running')
            try:
                result = self.textbox.start()
                self._call_in_main_thread(self.update_status, result, 'ready')
            except Exception as e:
                self._call_in_main_thread(self.update_status, f"生成失败: {e}", 'ready')
            finally:
                self._call_in_main_thread(self._set_ui_state, True)

        threading.Thread(target=worker, daemon=True).start()

    def action_delete_cache(self):
        # 该方法仍保留以防外部调用（但 UI 中已移除按钮）
        self.update_status("正在清除缓存...", 'running')
        try:
            self.textbox.delete(self.textbox.CACHE_PATH)
            self.update_status("缓存已清除，需要重新加载角色", 'ready')
        except Exception as e:
            self.update_status(f"清除缓存失败: {e}", 'ready')

    def action_pause(self):
        self.active = not self.active
        if not self.active:
            # 切换到暂停：记录当前选中角色 id（通过映射）
            try:
                sel = self.char_var.get()
                self.paused_char = self.display_to_id.get(sel) if hasattr(self, 'display_to_id') else (sel or None)
            except Exception:
                self.paused_char = None
            self.update_status("应用已暂停。", 'paused')
            self._set_ui_state(False)
        else:
            # 恢复：先启用 UI，再自动加载暂停前的角色（如果有）
            self._set_ui_state(True)
            self.update_status("应用已恢复，正在恢复角色...", 'running')
            if self.paused_char:
                try:
                    self.load_character_images(self.paused_char)
                except Exception:
                    pass
                finally:
                    self.paused_char = None
            else:
                self.update_status("应用已激活。", 'ready')

    def action_quit(self):
        # 取消全局热键（如果注册）
        try:
            if self.hotkey_registered and PLATFORM.startswith('win'):
                import keyboard
                try:
                    keyboard.clear_all_hotkeys()
                except Exception:
                    pass
        except Exception:
            pass
        # 写日志并销毁主窗口
        try:
            self._log("应用退出: " + datetime.datetime.now().isoformat())
        except Exception:
            pass
        try:
            self.root.destroy()
        except Exception:
            try:
                self.root.quit()
            except Exception:
                pass

    def center_window(self, win: tk.Tk | tk.Toplevel):
        """将给定窗口移动到屏幕中央（仅设置位置，不改变窗口大小以避免尺寸错误）"""
        try:
            win.update_idletasks()
            sw = win.winfo_screenwidth()
            sh = win.winfo_screenheight()
            # 优先使用当前已布局的真实像素尺寸，fallback 到请求尺寸
            w = win.winfo_width() or win.winfo_reqwidth() or 1
            h = win.winfo_height() or win.winfo_reqheight() or 1
            x = max(0, (sw - w) // 2)
            y = max(0, (sh - h) // 2)
            # 仅设置位置，避免改变窗口大小
            win.geometry(f"+{x}+{y}")
        except Exception:
            try:
                sw = win.winfo_screenwidth()
                sh = win.winfo_screenheight()
                x = sw // 2
                y = sh // 2
                win.geometry(f"+{x}+{y}")
            except Exception:
                pass

    # 新增：线程安全写日志，支持等级并格式化输出（兼容原调用）
    def _log(self, msg: str, level: str = "info"):
        """
        写入日志，格式：YYYY-MM-DD HH:MM:SS [level] : 信息
        level: info|warning|error（不区分大小写）
        容错且线程安全，不抛异常。
        """
        try:
            if msg is None:
                return
            lvl = (level or "info").lower()
            if lvl not in ("info", "warning", "error"):
                lvl = "info"
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            line = f"{timestamp} [{lvl}] : {msg}\n"

            lock = getattr(self, "_log_lock", None)
            logfile = getattr(self, "current_log_file", None)
            if lock is None or logfile is None:
                # 无法写入文件则降级到打印，避免抛异常阻塞主流程
                try:
                    print(line, end='')
                except Exception:
                    pass
                return

            # 使用锁确保多线程写入安全
            try:
                with lock:
                    try:
                        with open(logfile, 'a', encoding='utf-8') as fp:
                            fp.write(line)
                    except Exception:
                        # 尝试备用打开模式
                        try:
                            with open(logfile, 'a') as fp:
                                fp.write(line)
                        except Exception:
                            # 最后兜底打印
                            try:
                                print(line, end='')
                            except Exception:
                                pass
            except Exception:
                # 锁或写入过程中出错也要吞掉异常
                try:
                    print(line, end='')
                except Exception:
                    pass
        except Exception:
            # 保证不会因为日志写入而抛出异常
            pass


# 在文件末尾补充程序入口，保证可运行及优雅退出
if __name__ == "__main__":
    try:
        root = tk.Tk()
        app = ManosabaGUI(root)
        try:
            root.mainloop()
        except KeyboardInterrupt:
            try:
                app._log("KeyboardInterrupt 捕获，准备退出。")
            except Exception:
                pass
            try:
                app.action_quit()
            except Exception:
                pass
    except Exception as e:
        # 如果在创建 GUI 时抛异常，打印日志并尝试优雅退出
        try:
            print(f"应用启动失败: {e}")
        except Exception:
            pass
    finally:
        try:
            root.destroy()
        except Exception:
            pass
        try:
            sys.exit(0)
        except Exception:
            pass
