"""Place the desktop window inside the launch monitor's usable area."""
import logging
import os


def centered_bounds(work_area, scale=1):
    left, top, right, bottom = work_area
    available_width, available_height = right-left, bottom-top
    margin = max(0, min(round(16*scale), (available_width-1)//2, (available_height-1)//2))
    width = min(round(1440*scale), available_width-2*margin)
    height = min(round(940*scale), available_height-2*margin)
    return left+(available_width-width)//2, top+(available_height-height)//2, width, height


def center_before_show(window):
    if os.name != 'nt':
        return
    try:
        import ctypes
        from ctypes import wintypes
        from System.Drawing import Point, Rectangle, Size
        from System.Windows.Forms import Cursor, FormStartPosition, Screen

        native = window.native
        work = Screen.FromPoint(Cursor.Position).WorkingArea
        native.StartPosition = FormStartPosition.Manual
        # Move onto the target monitor before reading its per-window DPI.
        native.Location = Point(work.Left, work.Top)
        dpi_for_window = ctypes.windll.user32.GetDpiForWindow
        dpi_for_window.argtypes = [wintypes.HWND]
        dpi_for_window.restype = wintypes.UINT
        scale = dpi_for_window(native.Handle.ToInt64())/96 or 1
        x, y, width, height = centered_bounds((work.Left, work.Top, work.Right, work.Bottom), scale)
        native.MinimumSize = Size(min(round(780*scale), width), min(round(620*scale), height))
        native.Bounds = Rectangle(x, y, width, height)
    except Exception:
        logging.exception('Could not explicitly center desktop window')
