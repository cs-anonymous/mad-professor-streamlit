from fastapi import FastAPI, Request, Form, UploadFile
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from util.data_manager_clean import DataManager
from util.AI_manager_clean import AIManager
from fastapi.responses import FileResponse, HTMLResponse
from fastapi import HTTPException, UploadFile
import markdown
import os

app = FastAPI()
BASEDIR = os.path.dirname(os.path.abspath(__file__))
app.mount("/static", StaticFiles(directory=os.path.join(BASEDIR, "static")), name="static")
templates = Jinja2Templates(directory="templates")

# 初始化模块
data_manager = DataManager(BASEDIR)
ai_manager = AIManager()
data_manager.load_papers_index()

@app.get("/files/{path:path}")
def serve_file_or_dir(path: str):
    """处理任意深度的路径（文件或目录）"""
    full_path = os.path.join(BASEDIR, path)
    
    if os.path.isdir(full_path):
        # 如果是目录，返回文件列表
        files = os.listdir(full_path)
        files.sort()
        html = "<ul>" + "".join(
            f'<li><a href="/files/{os.path.join(path, f)}">{f}</a></li>'
            for f in files
        ) + "</ul>"
        return HTMLResponse(content=html)
    elif os.path.isfile(full_path):
        # 如果是文件，返回文件内容
        return FileResponse(full_path)
    else:
        raise HTTPException(status_code=404, detail="Not found")

# 路由配置
@app.get("/")
async def index(request: Request):
    papers = data_manager.papers_index
    # 添加默认选中论文参数
    return templates.TemplateResponse("index.html", {
        "request": request,
        "papers": papers,
        "selected_paper": papers[0]['id'] if papers else None
    })

@app.post("/upload")
async def upload_file(file: UploadFile):
    upload_dir = "uploads"
    os.makedirs(upload_dir, exist_ok=True)
    file_path = os.path.join(upload_dir, file.filename)
    with open(file_path, "wb") as f:
        f.write(await file.read())
    return {"filename": file.filename}

@app.get("/paper/{paper_id}")
async def get_paper_content(paper_id: str):
    paper = data_manager.load_paper_content(paper_id)
    extensions = ['fenced_code', 'tables'] 
    # 在前端使用 KaTeX 渲染 LaTeX 公式，后端不需要额外的处理
    # , 'pymdownx.arithmatex'
    
    return {
        "metadata": paper[0],
        "zh_content": markdown.markdown(paper[1], extensions=extensions),
        "en_content": markdown.markdown(paper[2], extensions=extensions)
    }

@app.post("/chat")
async def chat(prompt: str = Form(...), paper_id: str = Form(...)):
    response = ai_manager.get_ai_response(prompt, paper_id)
    return {"response": response}


if __name__ == "__main__":
    import uvicorn
    import os
    uvicorn.run("app:app", host="0.0.0.0", port=int(os.environ.get('PORT', 8502)), reload=True)