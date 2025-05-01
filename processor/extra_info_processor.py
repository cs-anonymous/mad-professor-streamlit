import json
import logging
from pathlib import Path
from util.config import LLMClient

SUMMARY_PROMPT_PATH = "prompt/summary_generation_prompt.txt"
QUESTION_PROMPT_PATH = "prompt/question_generation_prompt.txt"
GRAPH_QUESTION_PROMPT_PATH = "prompt/graph_question_generation_prompt.txt"
FORMULA_ANALYSIS_PROMPT_PATH = "prompt/formula_analysis_prompt.txt"

class ExtraInfoProcessor:
    """额外信息处理器，用于生成论文各章节的总结信息和问题"""

    def __init__(self):
        """初始化额外信息处理器"""
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self.llm = LLMClient()
        self.abstract_text = ""
        
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
        读取JSON文件，自下而上为各章节生成总结
        
        Args:
            input_path: 输入JSON文件路径
            output_path: 输出添加了总结的JSON文件路径
            
        Returns:
            Path: 输出文件路径
        """
        try:
            input_path = Path(input_path)
            output_path = Path(output_path)

            self.logger.info(f"开始生成章节总结: {input_path}")
            with input_path.open('r', encoding='utf-8') as f:
                data = json.load(f)
            
            # 提取摘要信息
            self.extract_abstract(data)
            
            # 从顶层章节开始，自下而上生成总结
            if "sections" in data:
                self.generate_section_summaries(data["sections"])
                
                # 生成问题阶段
                self.logger.info("开始生成各块内容的问题")
                self.generate_questions(data["sections"])
                self.logger.info("问题生成完成")

            # 写入输出文件
            with output_path.open('w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            self.logger.info(f"章节总结和问题生成完成，结果已保存到: {output_path}")
            return output_path
        except Exception as e:
            self.logger.error(f"章节总结和问题生成失败: {str(e)}", exc_info=True)
            raise
    
    def extract_abstract(self, data):
        """
        从数据中提取摘要信息并保存到类变量
        
        Args:
            data: 论文数据
        """
        if "sections" not in data:
            return
        
        for section in data["sections"]:
            if section.get("type") == "abstract":
                abstract_text = ""
                for item in section.get("content", []):
                    if isinstance(item, dict) and item.get("type") == "text" and item.get("translated_content"):
                        abstract_text += item["translated_content"] + "\n"
                
                if abstract_text:
                    self.abstract_text = abstract_text.strip()
                    self.logger.info("已提取摘要信息")
                    return
        
        self.logger.warning("未找到摘要信息")
    
    def generate_section_summaries(self, sections):
        """
        自下而上递归生成所有章节的总结
        
        Args:
            sections: 章节列表
            
        Returns:
            list: 当前层级所有章节的总结列表，每个元素为{"title": 章节标题, "summary": 章节总结}的字典
        """
        all_summaries = []
        
        for section in sections:
            # 跳过abstract和references类型的章节
            if section.get("type") in ["abstract", "references"]:
                self.logger.info(f"跳过 {section.get('title')} 章节的总结生成")
                continue
            
            # 收集子章节总结
            children_summaries = []
            if "children" in section and section["children"]:
                # 递归处理子章节，获取子章节的总结列表
                children_summaries = self.generate_section_summaries(section["children"])
                
            # 生成当前章节的总结
            self.logger.info(f"生成 {section.get('title', '未命名章节')} 的总结")
            section_summary = self.generate_summary_for_section(section, children_summaries)
            
            if section_summary:
                section["summary"] = section_summary
                # 将当前章节的标题和总结作为字典添加到列表中
                title = section.get('translated_title', section.get('title', '未命名章节'))
                all_summaries.append({"title": title, "summary": section_summary})
                
        return all_summaries
    
    def generate_summary_for_section(self, section, children_summaries=None):
        """
        为单个章节生成总结，综合考虑自身内容和子章节总结
        
        Args:
            section: 章节数据
            children_summaries: 子章节总结列表，每个元素为{"title": 章节标题, "summary": 章节总结}的字典
            
        Returns:
            str: 生成的章节总结
        """
        if children_summaries is None:
            children_summaries = []
            
        # 提取章节中所有翻译后的文本内容和formula内容
        contents = []
        for item in section.get("content", []):
            if isinstance(item, dict):
                if item.get("type") == "text" and item.get("translated_content"):
                    contents.append(item["translated_content"])
                elif item.get("type") == "formula" and item.get("content"):
                    contents.append(item['content'])
        
        # 如果没有内容且没有子章节总结，跳过总结生成
        if not contents and not children_summaries:
            self.logger.warning(f"章节 {section.get('title', '未命名章节')} 没有内容和子章节总结，跳过总结生成")
            return ""
        
        # 合并所有内容
        combined_text = "\n\n".join(contents) if contents else ""
        
        # 添加子章节总结信息（如果有），并包含章节标题
        children_summaries_text = ""
        if children_summaries:
            # 构建包含子章节标题的总结文本
            sub_summaries = []
            for child in children_summaries:
                sub_summaries.append(f"{child['title']}核心内容:\n{child['summary']}")
            
            children_summaries_text = "子章节：\n" + "\n\n".join(sub_summaries)
        
        # 合并当前章节内容和子章节总结，用于检查长度
        total_content = ""
        if combined_text:
            total_content += combined_text
        if children_summaries_text:
            total_content += "\n\n" + children_summaries_text if total_content else children_summaries_text
        
        # 如果总内容不超过100字符，直接使用总内容作为总结
        if len(total_content) <= 100:
            self.logger.info(f"章节 {section.get('title', '未命名章节')} 内容不超过100字符，直接使用原内容作为总结")
            return total_content.replace("\n", " ").strip()
        
        # 读取系统提示词
        system_prompt = self._read_file(SUMMARY_PROMPT_PATH)
        
        # 构建用户提示词
        user_prompt = f"章节标题: {section.get('translated_title', section.get('title', '未命名章节'))}\n\n"
        
        # 添加摘要作为背景信息
        if self.abstract_text:
            user_prompt += f"论文摘要背景:\n{self.abstract_text}\n\n"
        
        if combined_text:
            user_prompt += f"章节内容:\n{combined_text}\n\n"
            
        if children_summaries_text:
            user_prompt += f"{children_summaries_text}\n\n"
            
        user_prompt += "请根据要求生成这个章节的总结，只需输出总结文段，无需任何额外的解释说明:"
        
        # 调用LLM生成总结
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        try:
            summary = self.llm.chat(messages, stream=True).replace("\n", " ").strip()
            return summary
        except Exception as e:
            self.logger.error(f"生成章节 {section.get('title', '未命名章节')} 的总结失败: {str(e)}")
            return ""
    
    def generate_questions(self, sections):
        """
        为各个章节的内容块生成问题
        
        Args:
            sections: 章节列表
        """
        for section in sections:
            # 跳过abstract和references类型的章节
            if section.get("type") in ["abstract", "references"]:
                self.logger.info(f"跳过 {section.get('title')} 章节的问题生成")
                continue
            
            # 获取当前章节的summary，如果没有则使用abstract
            section_summary = section.get("summary", self.abstract_text)
            
            # 处理当前章节的内容块
            if "content" in section:
                self._process_content_blocks(section["content"], section_summary)
            
            # 递归处理子章节
            if "children" in section and section["children"]:
                self.generate_questions(section["children"])
    
    def _process_content_blocks(self, content_blocks, section_summary):
        """
        处理内容块，为每个块生成问题
        
        Args:
            content_blocks: 内容块列表
            section_summary: 章节摘要
        """
        # 处理连续的文本块
        i = 0
        while i < len(content_blocks):
            block = content_blocks[i]
            
            if isinstance(block, dict):
                block_type = block.get("type")
                
                if block_type == "text" and block.get("translated_content"):
                    # 处理文本块
                    questions = self._generate_questions_for_text(block["translated_content"], section_summary)
                    if questions:
                        block["questions"] = questions
                
                elif block_type in ["figure", "table"] and block.get("translated_caption"):
                    # 处理图片和表格块
                    questions = self._generate_questions_for_graph(
                        block["translated_caption"], 
                        section_summary,
                        block_type
                    )
                    if questions:
                        block["questions"] = questions
                
                elif block_type == "formula":
                    # 处理公式块，需要获取前后的文本上下文
                    context_before = self._find_text_context_backwards(content_blocks, i-1)
                    context_after = self._find_text_context_forwards(content_blocks, i+1)
                    
                    # 生成公式解析
                    formula_analysis = self._generate_formula_analysis(block.get("content", ""), context_before, context_after, section_summary)
                    if formula_analysis:
                        block["formula_analysis"] = formula_analysis
            
            i += 1
    
    def _generate_questions_for_text(self, text_content, section_summary):
        """
        为文本块生成问题
        
        Args:
            text_content: 文本内容
            section_summary: 章节摘要
            
        Returns:
            list: 生成的问题列表
        """
        if not text_content:
            return []
        
        # 读取问题生成提示词
        system_prompt = self._read_file(QUESTION_PROMPT_PATH)
        
        # 构建用户提示词
        user_prompt = f"上下文背景信息：{section_summary}\n需要生成问题的论文段落：{text_content}\n\n请根据要求生成问题："
        
        # 调用LLM生成问题
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        try:
            questions = self.llm.chat(messages, stream=True).replace("\n", " ").strip()
            return questions
        except Exception as e:
            self.logger.error(f"生成文本块问题失败: {str(e)}")
            return ""
    
    def _generate_questions_for_graph(self, caption, section_summary, graph_type):
        """
        为图片和表格块生成问题
        
        Args:
            caption: 图表说明
            section_summary: 章节摘要
            graph_type: 图表类型（"figure"或"table"）
            
        Returns:
            list: 生成的问题列表
        """
        if not caption:
            return []
        
        # 读取问题生成提示词
        system_prompt = self._read_file(GRAPH_QUESTION_PROMPT_PATH)
        
        # 根据图表类型设置提示词
        graph_type_text = "图片" if graph_type == "figure" else "表格"
        
        # 构建用户提示词
        user_prompt = f"上下文背景信息：{section_summary}\n需要生成问题的{graph_type_text}描述：{caption}\n\n请根据要求生成问题："
        
        # 调用LLM生成问题
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        try:
            questions = self.llm.chat(messages, stream=True).replace("\n", " ").strip()
            return questions
        except Exception as e:
            self.logger.error(f"生成{graph_type_text}块问题失败: {str(e)}")
            return ""
    
    def _find_text_context_backwards(self, content_blocks, start_index):
        """
        向后查找文本上下文（即向前查找）
        
        Args:
            content_blocks: 内容块列表
            start_index: 开始查找的索引
            
        Returns:
            str: 找到的文本上下文，如果没找到则返回空字符串
        """
        if start_index < 0:
            return ""
            
        for i in range(start_index, -1, -1):
            if (isinstance(content_blocks[i], dict) and 
                content_blocks[i].get("type") == "text" and 
                content_blocks[i].get("translated_content")):
                return content_blocks[i].get("translated_content", "")
        
        return ""
    
    def _find_text_context_forwards(self, content_blocks, start_index):
        """
        向前查找文本上下文（即向后查找）
        
        Args:
            content_blocks: 内容块列表
            start_index: 开始查找的索引
            
        Returns:
            str: 找到的文本上下文，如果没找到则返回空字符串
        """
        if start_index >= len(content_blocks):
            return ""
            
        for i in range(start_index, len(content_blocks)):
            if (isinstance(content_blocks[i], dict) and 
                content_blocks[i].get("type") == "text" and 
                content_blocks[i].get("translated_content")):
                return content_blocks[i].get("translated_content", "")
        
        return ""
    
    def _generate_formula_analysis(self, formula, context_before, context_after, section_summary):
        """
        为公式块生成详细解读和分析。

        Args:
            formula (str): 公式内容（LaTeX 或文本形式）
            context_before (str): 公式前的文本上下文
            context_after (str): 公式后的文本上下文
            section_summary (str): 当前章节的总结信息或摘要信息

        Returns:
            str: 生成的公式解析文本
        """
        if not formula:
            return ""

        # 读取系统提示词
        system_prompt = self._read_file(FORMULA_ANALYSIS_PROMPT_PATH)

        # 构建用户提示词，重点是让大模型结合前后文以及章节摘要，来解释公式的含义、符号意义、推导思路等
        user_prompt = f"""请对下列公式进行详细解读，并给出它在论文中的作用和意义。需要参考以下信息：

        章节背景摘要：
        {section_summary}

        公式前的文本上下文：
        {context_before}

        公式：
        {formula}

        公式后的文本上下文：
        {context_after}
        
        请根据要求生成这个公式的解析，只需输出解析文段，无需任何额外的解释说明："""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        try:
            # 调用 LLM 生成公式解析
            formula_analysis = self.llm.chat(messages, stream=True).replace("\n", " ").strip()
            return formula_analysis
        except Exception as e:
            self.logger.error(f"生成公式解析失败: {str(e)}")
            return ""
