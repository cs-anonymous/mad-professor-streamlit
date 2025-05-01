import json
import logging
from pathlib import Path
from util.config import LLMClient

# 翻译提示词文件路径
TITLE_TRANSLATE_PROMPT_PATH = "prompt/title_translate_prompt.txt"
CONTENT_TRANSLATE_PROMPT_PATH = "prompt/content_translate_prompt.txt"

class TranslateProcessor:
    """翻译处理器, 使用LLM进行对论文json文件分段翻译"""

    def __init__(self):
        """初始化翻译处理器"""
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self.llm = LLMClient()
        
        # 保存已翻译的摘要，用于后续翻译的上下文
        self.translated_abstract = ""
        
    def _read_file(self, filepath: str) -> str:
        """读取文件内容"""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return f.read().strip()
        except Exception as e:
            self.logger.warning(f"读取文件 {filepath} 失败: {str(e)}")
            return ""
        
    def process(self, input_path: str, output_path: str) -> Path:
        """
        读取 input.json，分阶段进行翻译。
        首先翻译所有title，然后翻译abstact，最后递归翻译每个章节的text和caption。
        """
        try:
            input_path = Path(input_path)
            output_path = Path(output_path)

            self.logger.info(f"开始翻译JSON文件: {input_path}")
            with input_path.open('r', encoding='utf-8') as f:
                data = json.load(f)
            
            # 1. 翻译标题
            self.translate_titles(data)
            
            # 2. 翻译abstract
            self.translate_abstract(data)
            
            # 3. 翻译sections内容
            self.translate_content(data)

            # 写入 output.json
            with output_path.open('w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            self.logger.info(f"翻译完成，结果已保存到: {output_path}")
            return output_path
        except Exception as e:
            self.logger.error(f"JSON处理失败: {str(e)}", exc_info=True)
            raise
    
    def translate_titles(self, data):
        """
        翻译JSON结构中的所有标题
        将翻译结果添加到对应层级title下的"translated_title"字段
        """
        # 翻译主标题
        if "title" in data:
            title = data["title"]
            self.logger.info(f"翻译主标题: {title}")
            data["translated_title"] = self.translate_text("title", title)
        
        # 递归翻译sections中的所有标题
        if "sections" in data:
            self.translate_section_titles(data["sections"])
    
    def translate_section_titles(self, sections):
        """递归翻译所有章节标题"""
        for section in sections:
            # 翻译当前章节标题
            if "title" in section:
                title = section["title"]
                self.logger.info(f"翻译章节标题: {title}")
                section["translated_title"] = self.translate_text("title", title)
            
            # 递归翻译子章节标题
            if "children" in section and section["children"]:
                self.translate_section_titles(section["children"])
    
    def translate_abstract(self, data):
        """翻译论文摘要"""
        # 查找abstract部分
        if not data.get("sections"):
            self.logger.warning("未找到sections，跳过摘要翻译")
            return
            
        for section in data["sections"]:
            if section.get("type") == "abstract":
                # 检查是否有内容
                if not (section.get("content") and section["content"]):
                    self.logger.warning("Abstract内容为空，跳过摘要翻译")
                    return
                    
                # 查找第一个type为text的content项
                abstract_text = ""
                for content_item in section["content"]:
                    if content_item.get("type") == "text":
                        abstract_text = content_item.get("content", "")
                        break
                        
                if not abstract_text:
                    self.logger.warning("Abstract中未找到text类型内容，跳过摘要翻译")
                    return
                
                # 翻译摘要
                self.logger.info("开始翻译摘要")
                translated_abstract = self.translate_text("abstract", abstract_text)
                
                # 保存翻译结果
                content_item["translated_content"] = translated_abstract
                self.translated_abstract = translated_abstract
                
                self.logger.info("摘要翻译完成")
                return
                
        self.logger.warning("未找到abstract部分，跳过摘要翻译")
    
    def translate_content(self, data):
        """翻译所有章节内容"""
        if "sections" in data:
            self.translate_section_content(data["sections"])
    
    def translate_section_content(self, sections):
        """递归翻译章节内容，包括文本和图表标题"""
        for section in sections:
            # 对于abstract部分，只处理图表和表格标题，跳过文本内容
            if section.get("type") == "abstract":
                self.logger.info("abstract部分: 只处理图表和表格标题")
                if "content" in section:
                    for item in section["content"]:
                        # 先检查item是否为字典类型
                        if not isinstance(item, dict):
                            self.logger.info(f"跳过非字典类型的内容: {str(item)[:50]}...")
                            continue
                        
                        # 根据类型处理不同内容
                        item_type = item.get("type")
                        
                        # 只处理图表和表格标题，跳过文本内容
                        if item_type in ["figure", "table"] and "caption" in item and item["caption"]:
                            caption = item["caption"]
                            self.logger.info(f"翻译abstract中的{item_type}标题: {caption[:50]}...")
                            item["translated_caption"] = self.translate_text("caption", caption, use_abstract_reference=True)
                continue

            # 翻译章节内容
            if "content" in section:
                # 用于保存章节内的前一段翻译，初始为空
                previous_section_translation = ""
                
                for item in section["content"]:
                    # 先检查item是否为字典类型
                    if not isinstance(item, dict):
                        self.logger.info(f"跳过非字典类型的内容: {str(item)[:50]}...")
                        continue

                    # 根据类型处理不同内容
                    item_type = item.get("type")
                    
                    # 处理文本内容
                    if item_type == "text" and "content" in item and item["content"]:
                        content = item["content"]
                        self.logger.info(f"翻译文本内容: {content[:50]}...")
                        
                        # 如果是章节的第一段文本且没有前一段参考，则使用abstract作为参考
                        if not previous_section_translation:
                            item["translated_content"] = self.translate_text("content", content, 
                                                                           previous_translation=None, 
                                                                           use_abstract_reference=True)
                        else:
                            # 否则使用前一段文本作为参考
                            item["translated_content"] = self.translate_text("content", content, 
                                                                           previous_translation=previous_section_translation, 
                                                                           use_abstract_reference=False)
                        
                        # 更新章节内的前一段翻译
                        previous_section_translation = item["translated_content"]
                    
                    # 处理图表和表格标题（使用abstract作为参考）
                    elif item_type in ["figure", "table"] and "caption" in item and item["caption"]:
                        caption = item["caption"]
                        self.logger.info(f"翻译{item_type}标题: {caption[:50]}...")
                        item["translated_caption"] = self.translate_text("caption", caption, use_abstract_reference=True)
                    
            # 递归翻译子章节 - 每个子章节有自己的翻译上下文
            if "children" in section and section["children"]:
                self.translate_section_content(section["children"])

    def translate_text(self, text_type, content, previous_translation=None, use_abstract_reference=False):
        """
        使用LLM翻译指定类型的文本
        
        参数:
        text_type: 文本类型 (title, abstract, content, caption)
        content: 需要翻译的内容
        previous_translation: 前一段文本的翻译（可选）
        use_abstract_reference: 是否使用abstract作为参考（图表和表格标题，或章节第一段）
        """
        # 根据文本类型选择对应的提示词文件路径
        prompt_file = TITLE_TRANSLATE_PROMPT_PATH if text_type == "title" else CONTENT_TRANSLATE_PROMPT_PATH
        
        # 读取系统提示词
        system_prompt = self._read_file(prompt_file)
        
        # 构建用户提示词
        if text_type == "title":
            user_prompt = f"需要翻译的标题:\n{content}\n\n直接输出："
        elif text_type == "abstract":
            user_prompt = f"需要翻译的内容:\n{content}\n\n直接输出："
        elif use_abstract_reference and self.translated_abstract:
            # 图表和表格标题或章节第一段使用abstract作为参考
            user_prompt = f"摘要翻译参考:\n{self.translated_abstract}\n\n需要翻译的内容:\n{content}\n\n直接输出："
        elif previous_translation:
            # 使用前一段文本作为参考（章节内的非第一段）
            user_prompt = f"前文翻译参考:\n{previous_translation}\n\n需要翻译的内容:\n{content}\n\n直接输出："
        else:
            # 如果没有任何参考，直接翻译
            user_prompt = f"需要翻译的内容:\n{content}\n\n直接输出："

        # 构建翻译提示并调用LLM进行翻译
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        return self.llm.chat(messages, stream=True).strip()