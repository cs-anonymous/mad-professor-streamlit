from pathlib import Path
import logging

from magic_pdf.data.data_reader_writer import FileBasedDataWriter, FileBasedDataReader
from magic_pdf.data.dataset import PymuDocDataset
from magic_pdf.model.doc_analyze_by_custom_model import doc_analyze

logger = logging.getLogger(__name__)

class PDFProcessor:
    """PDF处理器：将PDF转换为Markdown格式"""
    
    def __init__(self):
        """
        初始化PDF处理器
        """
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self.logger.debug("初始化PDF处理器")

    def process(self, pdf_path: str, output_dir: str) -> Path:
        """
        处理PDF文件
        
        Args:
            pdf_path: PDF文件路径
            output_dir: 输出目录路径

        Returns:
            Path: 生成的Markdown文件路径
        
        Raises:
            FileNotFoundError: 当PDF文件不存在时
        """
        pdf_path = Path(pdf_path)
        output_dir = Path(output_dir)
        
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF文件不存在: {pdf_path}")

        # try:
        # 设置输出路径
        print(f"[PDFProcessor] 开始处理PDF", pdf_path, output_dir)
        paper_name = pdf_path.stem
        output_image_path = output_dir / "images"
        local_image_path = 'images'
        
        # 初始化图片写入器
        image_writer = FileBasedDataWriter(str(output_image_path))
        md_writer = FileBasedDataWriter(str(output_dir))
        
        # 读取PDF文件
        reader = FileBasedDataReader("")
        pdf_bytes = reader.read(pdf_path)  # 读取PDF内容
        
        # 创建数据集实例
        ds = PymuDocDataset(pdf_bytes)
        
        # 处理PDF
        self.logger.info("开始PDF处理流程...")
        ds.apply(doc_analyze, ocr=True).pipe_ocr_mode(image_writer).dump_md(md_writer, f"{paper_name}.md", local_image_path)
        
        # 生成Markdown路径
        markdown_path = output_dir / f"{paper_name}.md"
        
        self.logger.info(f"Markdown文件已保存到: {markdown_path}")
        return markdown_path
            
        # except Exception as e:
        #     self.logger.error(f"PDF处理失败: {str(e)}", exc_info=True)
        #     raise
