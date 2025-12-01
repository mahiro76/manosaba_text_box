:: 项目根目录下运行此脚本
set ICON=assets\icon.ico

:: 可选：先安装依赖（只需第一次）
:: python -m pip install --upgrade pip
:: python -m pip install pyinstaller Pillow psutil pynput keyboard pyperclip pywin32

:: 清理旧构建
rd /s /q dist 2>nul
rd /s /q build 2>nul
del /f /q main_gui.spec 2>nul

if exist "%ICON%" (
  echo Icon found: %ICON% -- building with icon
  pyinstaller --noconfirm --onefile --windowed ^
    --name magia_textbox ^
    --add-data "assets;assets" ^
    --add-data "config;config" ^
    --add-data "requirements.txt;." ^
    --add-data "image_fit_paste.py;." ^
    --add-data "settings_dialog.py;." ^
    --add-data "text_fit_draw.py;." ^
    --hidden-import "pynput.keyboard" ^
    --hidden-import "PIL._imaging" ^
    --icon "%ICON%" ^
    main_gui.py
) else (
  echo WARNING: Icon not found: %ICON% -- building without icon
  pyinstaller --noconfirm --onefile --windowed ^
    --name magia_textbox ^
    --add-data "assets;assets" ^
    --add-data "config;config" ^
    --add-data "requirements.txt;." ^
    --add-data "image_fit_paste.py;." ^
    --add-data "settings_dialog.py;." ^
    --add-data "text_fit_draw.py;." ^
    --hidden-import "pynput.keyboard" ^
    --hidden-import "PIL._imaging" ^
    main_gui.py
)

echo Done. 可执行文件位于 dist\magia_textbox.exe
pause