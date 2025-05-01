import markdown
import os

def render_markdown(content: str, lang: str = 'zh', enable_katex: bool = True) -> str:
    """渲染Markdown内容，包含样式和公式支持"""
    # 使用与markdown_view.py相同的扩展配置
    extensions = ['fenced_code', 'tables']
    # , 'pymdownx.arithmatex'
    
    # 生成HTML内容
    html_content = markdown.markdown(content, extensions=extensions)
    
    # 构建完整HTML结构
    return """
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.4/dist/katex.min.css">
    <style>
        @font-face {
                font-family: 'Source Han Serif CN';
                src: url('https://n.ye-sun.com/app/font/SourceHanSerifCN-Regular-1.otf') format('opentype');
                font-weight: normal;
                font-style: normal;
            }
            
            @font-face {
                font-family: 'Source Han Serif CN';
                src: url('https://n.ye-sun.com/app/font/SourceHanSerifCN-Bold-2.otf') format('opentype');
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
    """ + f"""
    <div class="prose">
        {html_content}
    </div>
    """ + katex_scripts() if enable_katex else ""

# 注意script 必须在st.components.v1.html中，不能在st.markdown中
def katex_scripts():
    """生成KaTeX渲染脚本"""
    return """
    <script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.4/dist/katex.min.js"></script>
    <script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.4/dist/contrib/auto-render.min.js"></script>
    <script>
        document.addEventListener("DOMContentLoaded", function() {
            console.log('Attempting to render math...');
            renderMathInElement(document.body, {
                delimiters: [
                    {left: '$$', right: '$$', display: true},
                    {left: '$', right: '$', display: false}
                ]
            });
        });
    </script>
    """
