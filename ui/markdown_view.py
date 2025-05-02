import os
import markdown
import json
from util.data_manager import DataManager
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import QWebEnginePage
from PyQt6.QtCore import QUrl, pyqtSignal
from util.paths import get_font_path, get_asset_path

def get_paths(id):
    return {
        "article_en": f"{id}/final_en.md",
        "article_zh": f"{id}/final_zh.md",
        "rag_md": f"{id}/final_rag.md",
        "rag_tree": f"{id}/final_rag_tree.json",
        "rag_vector_store": f"{id}/vectors",
        "images": f"{id}/images",
    }

class CustomWebEnginePage(QWebEnginePage):
    """自定义WebEnginePage，可以重写特定的事件处理方法"""
    def __init__(self, parent=None):
        super().__init__(parent)

class MarkdownView(QWebEngineView):
    """
    Markdown视图，支持中英文切换、LaTeX渲染，
    以及获取可见内容和文本定位功能
    """
    # 定义信号
    visible_content_updated = pyqtSignal(dict)
    language_changed = pyqtSignal(str)
    
    def __init__(self, parent=None, data_manager:DataManager=None):
        """初始化MarkdownView组件"""
        super().__init__(parent)
        self.setStyleSheet("background-color: #ffffff;")
        
        # 保存数据管理器的引用
        self.data_manager = data_manager
        
        # 初始化状态变量
        self.current_lang = "zh"  # 默认为中文
        self.docs = {"en": "", "zh": ""}
        self.current_visible_content = None
        
        # 设置自定义页面
        custom_page = CustomWebEnginePage(self)
        self.setPage(custom_page)
        
        # 连接加载完成信号
        self.loadFinished.connect(self.on_load_finished)
        
        # 设置样式表
        self.setup_css()
    
    def setup_css(self):
        """设置页面样式表"""
        self.css = """
        <style>
            @font-face {
                font-family: 'Source Han Serif CN';
                src: url('file:///FONT_PATH_REGULAR') format('opentype');
                font-weight: normal;
                font-style: normal;
            }
            
            @font-face {
                font-family: 'Source Han Serif CN';
                src: url('file:///FONT_PATH_BOLD') format('opentype');
                font-weight: bold;
                font-style: normal;
            }
            
            body {
                font-family: 'Source Han Serif CN', 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, 'Open Sans', 'Helvetica Neue', sans-serif;
                line-height: 1.6;
                color: #333;
                max-width: 100%;
                padding: 0 20px;
                margin: 0 auto;
                background-color: #fafafa;
                border-radius: 10px;
            }
            
            /* 添加科技感的样式 */
            h1 {
                color: #1a237e;
                border-bottom: 2px solid #3949ab;
                padding-bottom: 0.2em;
                margin-top: 1.5em;
                font-weight: bold;
                position: relative;
            }
            
            h1:after {
                content: "";
                position: absolute;
                bottom: -2px;
                left: 0;
                width: 50px;
                height: 2px;
                background: linear-gradient(90deg, #3949ab, #1a237e);
            }
            
            h2 {
                color: #283593;
                border-bottom: 1px solid #5c6bc0;
                padding-bottom: 0.2em;
            }
            
            h3 {
                color: #303f9f;
            }
            
            a {
                color: #3949ab;
                text-decoration: none;
                border-bottom: 1px dotted #3949ab;
                transition: all 0.3s ease;
            }
            
            a:hover {
                color: #5c6bc0;
                border-bottom: 1px solid #5c6bc0;
            }
            
            pre {
                background-color: #e8eaf6;
                border-left: 4px solid #3949ab;
                padding: 1em;
                overflow-x: auto;
                border-radius: 8px;
            }
            
            code {
                font-family: Consolas, Monaco, 'Andale Mono', monospace;
                background-color: #e8eaf6;
                padding: 0.2em 0.4em;
                border-radius: 4px;
                color: #283593;
            }
            
            blockquote {
                border-left: 4px solid #5c6bc0;
                padding: 0.5em 1em;
                margin-left: 0;
                background-color: #e8eaf6;
                color: #3949ab;
                border-radius: 6px;
            }
            
            table {
                border-collapse: collapse;
                width: 100%;
                margin: 1em 0;
                border: 1px solid rgba(0,0,0,0.1);
                border-radius: 6px;
                overflow: hidden;
            }
            
            table th {
                background-color: #3949ab;
                color: white;
                padding: 0.5em;
                text-align: left;
            }
            
            table td {
                padding: 0.5em;
                border-bottom: 1px solid #c5cae9;
            }
            
            table tr:nth-child(even) {
                background-color: #e8eaf6;
            }
            
            img {
                max-width: 100%;
                border: 1px solid rgba(0,0,0,0.1);
                border-radius: 8px;
                margin: 1em 0;
            }
            
            /* KaTeX容器样式 */
            .arithmatex {
                overflow-x: auto;
                max-width: 100%;
            }
            
            .katex-display > .katex {
                max-width: 100%;
                overflow-x: auto;
                overflow-y: hidden;
                padding: 5px 0;
            }
        </style>
        """
    
    def on_load_finished(self, success):
        """页面加载完成后的处理"""
        if success:
            # 页面加载成功后，获取初始可见内容
            self.get_visible_content()
            
            # 添加滚动事件监听器
            self.add_scroll_listener()
    
    def add_scroll_listener(self):
        """添加JavaScript滚动事件监听器"""
        js_code = """
        (function() {
            // 移除现有的滚动监听器(如果有)
            if (window._scrollHandler) {
                window.removeEventListener('scroll', window._scrollHandler);
            }
            
            // 创建带有防抖动的滚动处理函数
            window._scrollTimer = null;
            window._scrollHandler = function() {
                if (window._scrollTimer !== null) {
                    clearTimeout(window._scrollTimer);
                }
                window._scrollTimer = setTimeout(function() {
                    // 通知Qt应用滚动已经发生
                    window.scrollNotification = new Date().getTime();
                    // 该变量的变化会被Qt检测到
                }, 200);  // 200ms防抖动
            };
            
            // 添加滚动事件监听器
            window.addEventListener('scroll', window._scrollHandler);
            
            // 监视变量
            window.scrollNotification = 0;
            
            return "已添加滚动监听器";
        })();
        """
        self.page().runJavaScript(js_code, self._handle_add_scroll_listener_result)
    
    def _handle_add_scroll_listener_result(self, result):
        """处理添加滚动监听器的结果"""
        # 设置定时检查滚动通知变量
        from PyQt6.QtCore import QTimer
        self.scroll_check_timer = QTimer(self)
        self.scroll_check_timer.timeout.connect(self.check_scroll_notification)
        self.scroll_check_timer.start(300)  # 每300ms检查一次
    
    def check_scroll_notification(self):
        """检查滚动通知变量是否已更新"""
        js_code = "window.scrollNotification || 0;"
        self.page().runJavaScript(js_code, self._handle_scroll_notification)
    
    def _handle_scroll_notification(self, timestamp):
        """处理滚动通知时间戳"""
        if not hasattr(self, '_last_scroll_timestamp'):
            self._last_scroll_timestamp = 0
        
        # 添加对 None 值的检查
        if timestamp is None:
            return
            
        if timestamp > self._last_scroll_timestamp:
            self._last_scroll_timestamp = timestamp
            # 滚动已经发生，获取可见内容
            self.get_visible_content()
    
    def get_visible_content(self):
        """
        获取当前在视图中可见的内容
        
        Returns:
            None: 执行JS代码来获取可见内容，结果通过回调函数处理
        """
        js_code = """
        (function() {
            // 获取可视区域范围
            var viewportHeight = window.innerHeight;
            var viewportTop = window.scrollY;
            var viewportBottom = viewportTop + viewportHeight;
            
            // 获取所有文本元素
            var textElements = Array.from(document.querySelectorAll('p, h1, h2, h3, h4, h5, h6, li, blockquote, pre, table, code, a, .arithmatex, .katex-display:not(.arithmatex *)'));
            
            // 获取文档总高度
            var documentHeight = Math.max(
                document.body.scrollHeight,
                document.body.offsetHeight,
                document.documentElement.clientHeight,
                document.documentElement.scrollHeight,
                document.documentElement.offsetHeight
            );
            
            // 筛选当前在视口中的元素
            var visibleElements = textElements.filter(function(el) {
                var rect = el.getBoundingClientRect();
                // 元素顶部在视口内 或 元素底部在视口内 或 元素完全包含视口
                return (rect.top >= 0 && rect.top <= viewportHeight) || 
                       (rect.bottom >= 0 && rect.bottom <= viewportHeight) ||
                       (rect.top < 0 && rect.bottom > viewportHeight);
            });
            
            // 提取可见元素的文本内容和HTML
            var visibleContent = visibleElements.map(function(el) {
                var computedStyle = window.getComputedStyle(el);
                
                // 创建用于清理HTML的函数
                function cleanHtmlContent(element) {
                    // 创建临时DOM元素
                    var tempDiv = document.createElement('div');
                    tempDiv.innerHTML = element.outerHTML;
                    
                    // 移除所有LaTeX相关元素
                    var mathElements = tempDiv.querySelectorAll('.arithmatex, .katex, .katex-display');
                    mathElements.forEach(function(mathEl) {
                        mathEl.parentNode.removeChild(mathEl);
                    });
                    
                    // 获取纯文本内容（自动去除HTML标签）
                    return tempDiv.textContent.trim();
                }
                
                // 判断是否是LaTeX元素
                var isLatex = el.classList.contains('arithmatex') || 
                            el.classList.contains('katex') || 
                            el.classList.contains('katex-display');
                
                return {
                    tag: el.tagName.toLowerCase(),
                    text: el.innerText.trim(),
                    html: el.outerHTML,
                    cleanText: isLatex ? '' : cleanHtmlContent(el), // 如果是LaTeX元素则返回空字符串
                    isFullyVisible: (el.getBoundingClientRect().top >= 0 && 
                                    el.getBoundingClientRect().bottom <= viewportHeight)
                };
            });
            
            // 提取包含所有可见内容的原始文本，按文档顺序排序
            visibleElements.sort(function(a, b) {
                var aRect = a.getBoundingClientRect();
                var bRect = b.getBoundingClientRect();
                
                // 首先按顶部位置排序
                if (aRect.top < bRect.top) return -1;
                if (aRect.top > bRect.top) return 1;
                
                // 如果顶部位置相同，按左侧位置排序
                if (aRect.left < bRect.left) return -1;
                if (aRect.left > bRect.left) return 1;
                
                return 0;
            });
            
            // 提取所有可见元素的原始文本作为单个字符串
            var fullVisibleText = "";
            var lastTag = "";
            
            visibleElements.forEach(function(el) {
                var text = el.innerText.trim();
                if (!text) return;  // 跳过空元素
                
                var tag = el.tagName.toLowerCase();
                // 简化公式类型识别，直接基于KaTeX的类名
                var isBlockFormula = el.classList.contains('katex-display');
                var isInlineFormula = el.classList.contains('katex') && !el.classList.contains('katex-display');
                
                // 根据元素类型添加适当的格式
                if (isBlockFormula) {
                    // 块级公式：前后加换行，去掉空格
                    fullVisibleText += "\\n" + text.replace(/\s+/g, '') + "\\n";
                } else if (isInlineFormula) {
                    // 行内公式：去掉空格
                    fullVisibleText += text.replace(/\s+/g, '');
                } else if (tag === 'h1' || tag === 'h2' || tag === 'h3' || tag === 'h4' || tag === 'h5' || tag === 'h6') {
                    // 为标题添加换行
                    fullVisibleText += "\\n" + text + "\\n";
                } else if (tag === 'li') {
                    // 为列表项添加项目符号
                    fullVisibleText += "• " + text + "\\n";
                } else if (tag === 'p' || tag === 'blockquote') {
                    // 为段落添加换行
                    fullVisibleText += text + "\\n\\n";
                } else if (tag === 'pre' || tag === 'code') {
                    // 为代码块添加格式
                    fullVisibleText += "```\\n" + text + "\\n```\\n";
                } else {
                    // 其他元素
                    fullVisibleText += text + " ";
                }
                
                lastTag = tag;
            });
            
            // 获取当前滚动进度
            var scrollProgress = (viewportTop + viewportHeight/2) / documentHeight * 100;
            
            return JSON.stringify({
                scrollProgress: scrollProgress,
                visibleContent: visibleContent,
                fullVisibleText: fullVisibleText.trim()
            });
        })();
        """
        
        # 执行JavaScript代码并设置回调来处理结果
        self.page().runJavaScript(js_code, self._handle_visible_content_result)
    
    def _handle_visible_content_result(self, result):
        """
        处理获取可见内容的JavaScript执行结果
        
        Args:
            result: JS执行的结果，JSON字符串
        """
        if result:
            try:
                data = json.loads(result)
                
                # 发出信号，通知其他组件可见内容已更新
                self.visible_content_updated.emit(data)
                
                # 保存当前可见内容的状态
                self.current_visible_content = data
                
            except json.JSONDecodeError as e:
                print(f"解析可见内容数据失败: {e}")
        else:
            print("获取可见内容失败: 空结果")
    
    def _handle_scroll_result(self, found):
        """处理滚动操作的结果"""
        if not found:
            # 如果没有找到匹配内容，可以显示提示
            print("未找到匹配的内容")
    
    def load_markdown(self, md_content, lang="zh", render=True):
        """
        加载Markdown内容
        
        Args:
            md_content: Markdown格式的文本内容
            lang: 语言代码，默认为'zh'（中文）
            render: 是否立即渲染，默认为True
        """
        self.docs[lang] = md_content
        if render:
            self.current_lang = lang
            self._render_markdown()
    
    def toggle_language(self):
        """
        切换显示语言
        
        在中文和英文之间切换，并重新渲染文档
        
        Returns:
            str: 当前语言代码
        """
        self.current_lang = "en" if self.current_lang == "zh" else "zh"
        self._render_markdown()
        self.language_changed.emit(self.current_lang)
        return self.current_lang
    
    def set_language(self, lang):
        """
        设置当前显示语言并重新渲染
        
        Args:
            lang: 语言代码，'zh'或'en'
        
        Returns:
            str: 当前语言代码
        """
        if lang in ['zh', 'en']:
            self.current_lang = lang
            self._render_markdown()
            self.language_changed.emit(self.current_lang)
        return self.current_lang
    
    def get_current_language(self):
        """
        获取当前显示语言
        
        Returns:
            str: 当前语言代码
        """
        return self.current_lang
    
    def set_data_manager(self, data_manager):
        """设置数据管理器引用"""
        self.data_manager = data_manager
    
    def _render_markdown(self):
        """
        渲染Markdown内容为HTML
        
        将当前语言的Markdown内容转换为HTML并使用KaTeX显示LaTeX公式
        """
        # 检查当前语言是否有内容
        if not self.docs[self.current_lang]:
            # 如果当前语言没有内容，显示简单提示
            html_content = f"<p>没有可用的{self.current_lang}内容</p>" if self.current_lang == "zh" else "<p>No content available in English</p>"
        else:
            # 预处理Markdown内容，处理图片路径
            content = self.docs[self.current_lang]
            
            # 使用增强的markdown配置，添加arithmatex扩展专门处理LaTeX公式
            html_content = markdown.markdown(
                content,
                extensions=[
                    'tables', 'fenced_code', 'codehilite', 'extra',
                    'pymdownx.arithmatex'  # 专门处理LaTeX的扩展
                ],
                extension_configs={
                    'pymdownx.arithmatex': {
                        'generic': True  # 让KaTeX接管所有LaTeX处理
                    }
                }
            )
        
        # 获取字体路径
        font_path_regular = get_font_path("SourceHanSerifCN-Regular-1.otf")
        font_path_bold = get_font_path("SourceHanSerifCN-Bold-2.otf")
        
        # 替换CSS中的字体URL为绝对路径
        css_with_paths = self.css.replace("FONT_PATH_REGULAR", font_path_regular.replace(os.sep, '/'))
        css_with_paths = css_with_paths.replace("FONT_PATH_BOLD", font_path_bold.replace(os.sep, '/'))

        # 获取KaTeX资源的本地路径
        katex_css_path = get_asset_path("katex/katex.min.css")
        katex_js_path = get_asset_path("katex/katex.min.js")
        katex_autorender_path = get_asset_path("katex/contrib/auto-render.min.js")
        
        # 将路径转换为本地文件URL
        katex_css_url = QUrl.fromLocalFile(katex_css_path).toString()
        katex_js_url = QUrl.fromLocalFile(katex_js_path).toString()
        katex_autorender_url = QUrl.fromLocalFile(katex_autorender_path).toString()
        
        # 构建完整HTML，使用KaTeX进行LaTeX支持
        full_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            {css_with_paths}
            
            <!-- KaTeX CSS -->
            <link rel="stylesheet" href="{katex_css_url}">
            
            <!-- KaTeX JS -->
            <script defer src="{katex_js_url}"></script>
            <script defer src="{katex_autorender_url}"></script>
            <script>
                document.addEventListener("DOMContentLoaded", function() {{
                    renderMathInElement(document.body, {{
                        // 自定义分隔符
                        delimiters: [
                            {{left: '$$', right: '$$', display: true}},
                            {{left: '$', right: '$', display: false}},
                            {{left: '\\\\(', right: '\\\\)', display: false}},
                            {{left: '\\\\[', right: '\\\\]', display: true}}
                        ],
                        throwOnError: false,
                        output: "html",
                        strict: false,
                        trust: true
                    }});
                }});
            </script>
        </head>
        <body>
            {html_content}
        </body>
        </html>
        """
        
        # 获取当前文档的基本路径作为基本URL
        base_url = None
        if hasattr(self, 'data_manager') and self.data_manager and self.data_manager.current_paper:
            paper = self.data_manager.current_paper
            paths = get_paths(paper['id'])
            paper_path = paths.get(f'article_{self.current_lang}', '')
            if paper_path:
                paper_dir = os.path.dirname(os.path.join(
                    self.data_manager.output_dir,
                    paper_path
                ))
                base_url = QUrl.fromLocalFile(paper_dir + '/')
        
        # 如果没有找到基本URL（如欢迎界面的情况），使用资源目录作为基本URL
        if not base_url:
            # 获取assets/katex所在目录的上级目录作为基本URL
            katex_dir = os.path.dirname(os.path.dirname(get_asset_path("katex/katex.min.js")))
            base_url = QUrl.fromLocalFile(katex_dir + '/')
        
        # 设置HTML内容及基本URL
        if base_url:
            self.setHtml(full_html, base_url)
        else:
            self.setHtml(full_html)
            
    def get_current_visible_text(self):
        """
        获取当前可见的文本内容
        
        Returns:
            str: 当前可见的文本内容，如果尚未获取到则返回空字符串
        """
        if self.current_visible_content:
            return self.current_visible_content.get('fullVisibleText', '')
        return ''
    
    def toggle_language(self):
        """
        切换显示语言并同步阅读位置
        """
        # 如果数据管理器存在且已加载论文
        if hasattr(self, 'data_manager') and self.data_manager and self.data_manager.current_paper:
            # 获取当前第一个可见元素的内容、类型
            element_text, element_type = self._extract_first_visible_element()
            
            # 切换语言
            new_lang = "en" if self.current_lang == "zh" else "zh"
            old_lang = self.current_lang
            self.current_lang = new_lang
            
            # 渲染新语言内容
            self._render_markdown()
            
            # 如果有有效的元素内容，尝试找到对应位置
            if element_text and element_type:
                # 查找匹配内容，传递元素类型
                target_content, element_type = self.data_manager.find_matching_content(element_text, old_lang, element_type)
                
                if target_content:
                    # 滚动到匹配位置
                    self.page().loadFinished.connect(
                        lambda ok: self._scroll_to_matching_content(target_content, element_type) if ok else None)
        else:
            # 如果不是在查看论文，简单切换语言
            self.current_lang = "en" if self.current_lang == "zh" else "zh"
            self._render_markdown()
        
        # 发送语言变更信号
        self.language_changed.emit(self.current_lang)
        return self.current_lang

    def _extract_first_visible_element(self):
        """
        从当前可见内容中提取第一个有效元素
        
        Returns:
            tuple: (元素干净文本内容, 元素类型) 元素类型为 'title', 'text' 或 'table' 
        """
        if not self.current_visible_content or not self.current_visible_content.get('visibleContent'):
            return None, None
            
        # 获取可见元素列表，已按位置排序
        visible_elements = self.current_visible_content.get('visibleContent', [])
        
        # 遍历可见元素，找到第一个有效内容
        for element in visible_elements:
            tag = element.get('tag', '')
            clean_text = element.get('cleanText', '').strip()
            
            # 跳过LaTeX元素和空元素
            if not clean_text:
                continue
                
            # 根据元素标签确定类型
            element_type = None
            
            if tag in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
                element_type = 'title'
            elif tag == 'table':
                element_type = 'table'
            else:
                element_type = 'text'
            
            return clean_text, element_type

    def _scroll_to_matching_content(self, target_content, content_type):
        """
        滚动到匹配内容的位置
        
        Args:
            target_content, content_type: 内容,类型
        """
        
        if not target_content:
            print("没有目标内容，无法滚动")
            return
            
        # 清理LaTeX和HTML标签，准备搜索
        def clean_for_search(text):
            import re
            # 移除HTML标签
            text = re.sub(r'</?[a-zA-Z][a-zA-Z0-9]*(\s+[^>]*)?>', ' ', text)
            # 移除LaTeX公式
            text = re.sub(r'\$\$[^$]*\$\$', ' ', text)
            text = re.sub(r'\$[^$]*\$', ' ', text) 
            # 移除其他LaTeX表示
            text = re.sub(r'\\[\(\[][^\\]*\\[\)\]]', ' ', text)

            # 处理可能破坏JavaScript字符串的特殊字符
            # 移除引号、反斜杠、换行符等
            text = re.sub(r'["\'\\]', '', text)  # 移除引号和反斜杠
            text = re.sub(r'[\n\r\t]', ' ', text)  # 将换行符和制表符替换为空格
            # 规范化空白
            text = re.sub(r'\s+', ' ', text).strip()
            return text
        
        # 清理整个目标内容用于搜索
        search_text = clean_for_search(target_content)
        
        # 根据内容类型选择不同的搜索策略
        js_code = f"""
        (function() {{
            // 给页面一点时间完全渲染
            setTimeout(function() {{
                // 准备清理函数
                function cleanHtmlContent(element) {{
                    // 创建临时DOM元素
                    var tempDiv = document.createElement('div');
                    tempDiv.innerHTML = element.outerHTML;
                    
                    // 移除所有LaTeX相关元素
                    var mathElements = tempDiv.querySelectorAll('.arithmatex, .katex, .katex-display');
                    mathElements.forEach(function(mathEl) {{
                        mathEl.parentNode.removeChild(mathEl);
                    }});
                    
                    // 获取纯文本内容（自动去除HTML标签）
                    return tempDiv.textContent.trim();
                }}
                
                // 标准化文本：只保留中文、英文字母和数字
                function normalizeText(text) {{
                    // 保留中文字符(\u4e00-\u9fff)、英文字母和数字
                    return text.toLowerCase().replace(/[^\u4e00-\u9fff\w\d]/g, '');
                }}
                
                // 改进的文本匹配函数 - 检查包含关系
                function textMatch(elementText, searchText) {{
                    if (!elementText || !searchText) return false;
                    
                    // 标准化两个字符串 - 只保留中英文和数字
                    var normElement = normalizeText(elementText);
                    var normSearch = normalizeText(searchText);
                    
                    // 检查子串关系（双向）
                    return normElement.includes(normSearch) || normSearch.includes(normElement);
                }}
                
                // 搜索文本
                var searchText = "{search_text}";
                var contentType = "{content_type}";
                var foundElement = null;
                
                // 根据内容类型选择搜索范围
                var elements;
                if (contentType === 'title') {{
                    // 标题搜索
                    elements = Array.from(document.querySelectorAll('h1, h2, h3, h4, h5, h6'));
                }} else if (contentType === 'table') {{
                    // 表格搜索
                    elements = Array.from(document.querySelectorAll('table'));
                }} else {{
                    // 文本搜索 - 默认
                    elements = Array.from(document.querySelectorAll('p, li, blockquote, pre'));
                }}
                
                // 查找匹配元素
                for (var i = 0; i < elements.length; i++) {{
                    var element = elements[i];
                    var cleanText = cleanHtmlContent(element);
                    
                    if (textMatch(cleanText, searchText)) {{
                        foundElement = element;
                        console.log("找到匹配元素:", contentType, cleanText.substring(0, 50) + (cleanText.length > 50 ? "..." : ""));
                        break;
                    }}
                }}
                
                // 如果找到匹配元素，滚动到该元素
                if (foundElement) {{
                    // 获取元素位置
                    var rect = foundElement.getBoundingClientRect();
                    var scrollTop = window.pageYOffset || document.documentElement.scrollTop;
                    
                    // 计算目标位置（使元素位于视口中央偏上）
                    var targetY = rect.top + scrollTop - (window.innerHeight * 0.3);
                    
                    // 滚动到目标位置（带平滑效果）
                    window.scrollTo({{
                        top: targetY,
                        behavior: 'smooth'
                    }});
                    
                    // 高亮显示找到的元素
                    var originalBackground = foundElement.style.backgroundColor;
                    var originalTransition = foundElement.style.transition;
                    
                    foundElement.style.transition = "background-color 0.5s ease";
                    foundElement.style.backgroundColor = "#FFFF99";
                    
                    // 一段时间后恢复原有样式
                    setTimeout(function() {{
                        foundElement.style.backgroundColor = originalBackground;
                        setTimeout(function() {{
                            foundElement.style.transition = originalTransition;
                        }}, 250);
                    }}, 500);
                    
                    return true;
                }} else {{
                    console.log("未找到匹配元素:", contentType, searchText.substring(0, 50) + (searchText.length > 50 ? "..." : ""));
                }}
                 
                return false;
            }}, 250);  // 给页面250毫秒的时间完成渲染
        }})();
        """
        
        self.page().runJavaScript(js_code)