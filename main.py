import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QFontDatabase, QFont, QPalette, QColor, QIcon, QPixmap, QPainter, QBrush, QLinearGradient
from PyQt6.QtCore import Qt, QRect, QPoint
from util.paths import get_font_path
from ui.AI_professor_UI import AIProfessorUI

def generate_app_icon():
    """生成应用程序图标"""
    # 创建图标画布
    icon_size = 64
    pixmap = QPixmap(icon_size, icon_size)
    pixmap.fill(Qt.GlobalColor.transparent)  # 透明背景
    
    # 创建画笔
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    
    # 创建渐变背景
    gradient = QLinearGradient(0, 0, icon_size, icon_size)
    gradient.setColorAt(0, QColor(13, 71, 161))  # 深蓝色 #0D47A1
    gradient.setColorAt(0.5, QColor(26, 35, 126))  # 深靛蓝 #1A237E
    gradient.setColorAt(1, QColor(13, 71, 161))  # 深蓝色 #0D47A1
    
    # 绘制圆形背景
    painter.setBrush(QBrush(gradient))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawEllipse(4, 4, icon_size-8, icon_size-8)
    
    # 绘制书本图案
    painter.setPen(Qt.GlobalColor.white)
    painter.setBrush(QBrush(QColor(255, 255, 255, 180)))
    
    # 绘制书本封面
    book_rect = QRect(18, 16, 28, 32)
    painter.drawRect(book_rect)
    
    # 绘制书页
    painter.setBrush(QBrush(QColor(240, 240, 240)))
    page_rect = QRect(16, 18, 28, 29)
    painter.drawRect(page_rect)
    
    # 绘制书脊线条
    for i in range(4):
        y = 22 + i * 6
        painter.drawLine(QPoint(16, y), QPoint(44, y))
    
    # 绘制AI图标（简化的"AI"文字）
    painter.setFont(QFont("Arial", 14, QFont.Weight.Bold))
    painter.setPen(QColor(26, 35, 126))  # 深靛蓝色
    painter.drawText(QRect(20, 20, 20, 20), Qt.AlignmentFlag.AlignCenter, "AI")
    
    # 结束绘制
    painter.end()
    
    # 创建图标
    return QIcon(pixmap)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    app.setStyle('Fusion')  # 使用Fusion风格以获得更现代的外观
    
    # 生成并设置应用程序图标
    app_icon = generate_app_icon()
    app.setWindowIcon(app_icon)
    
    # 如果是Windows系统，设置任务栏图标ID
    if sys.platform == "win32":
        import ctypes
        app_id = 'ai.professor.paperassistant.1.0'  # 应用程序唯一标识符
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
    
    # 注册字体
    # UI使用思源黑体
    font_id_regular = QFontDatabase.addApplicationFont(get_font_path("SourceHanSansSC-Regular-2.otf"))
    font_id_bold = QFontDatabase.addApplicationFont(get_font_path("SourceHanSansSC-Bold-2.otf"))
    
    # 注册Markdown字体
    # Markdown用的思源宋体
    QFontDatabase.addApplicationFont(get_font_path("SourceHanSerifCN-Regular-1.otf"))
    QFontDatabase.addApplicationFont(get_font_path("SourceHanSerifCN-Bold-2.otf"))

    # 检查字体是否加载成功
    if font_id_regular != -1 and font_id_bold != -1:
        font_family_regular = QFontDatabase.applicationFontFamilies(font_id_regular)[0]
        font_family_bold = QFontDatabase.applicationFontFamilies(font_id_bold)[0]
        
        # 设置应用程序默认字体
        default_font = QFont(font_family_regular, 10)
        app.setFont(default_font)
    else:
        print("无法加载自定义字体，使用系统默认字体")
    
    # 设置应用程序级别的调色板，使界面更加现代
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(240, 240, 240))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(51, 51, 51))
    palette.setColor(QPalette.ColorRole.Base, QColor(255, 255, 255))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(245, 245, 245))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(255, 255, 255))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor(51, 51, 51))
    palette.setColor(QPalette.ColorRole.Text, QColor(51, 51, 51))
    palette.setColor(QPalette.ColorRole.Button, QColor(240, 240, 240))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(51, 51, 51))
    palette.setColor(QPalette.ColorRole.Link, QColor(42, 130, 218))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(42, 130, 218))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor(255, 255, 255))
    
    app.setPalette(palette)
    
    window = AIProfessorUI()
    window.show()
    sys.exit(app.exec())