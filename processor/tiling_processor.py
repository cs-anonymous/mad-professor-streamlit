import json
import logging
import re
import numpy as np
from pathlib import Path
from typing import Dict, List, Any
from sklearn.metrics.pairwise import cosine_similarity
from util.config import EmbeddingModel

class TilingProcessor:
    """
    JSON文件分块处理器
    
    将处理后的JSON文件进行分割合并处理，为翻译阶段做准备
    使用向量相似度计算最佳切分点
    """
    
    def __init__(self, min_length: int = 500, max_length: int = 2500, window_size: int = 3, step_size: int = 1):
        """
        初始化平铺处理器
        
        Args:
            min_length: 文本块最小长度
            max_length: 文本块最大长度
            window_size: 相似度计算窗口大小
            step_size: 滑动窗口步长
        """
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self.min_length = min_length
        self.max_length = max_length
        self.window_size = window_size
        self.step_size = step_size
    
    def process(self, input_path: str, output_path: str) -> Path:
        """
        处理JSON文件，将文本块进行合并分割处理
        
        Args:
            input_path: 输入JSON文件路径
            output_path: 输出JSON文件路径
            
        Returns:
            Path: 输出文件路径
        """
        self.logger.info(f"开始处理JSON文件: 从 {input_path} 到 {output_path}")
        
        # 读取输入JSON文件
        with open(input_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # 处理sections中的content
        if 'sections' in data:
            self.logger.info(f"开始处理文档sections，共 {len(data['sections'])} 个section")
            self._process_sections(data['sections'])
            self.logger.info("sections处理完成")
        
        # 保存处理后的JSON文件
        output_file = Path(output_path)
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        self.logger.info(f"处理完成，输出已保存到 {output_file}")
        return output_file
    
    def _process_sections(self, sections: List[Dict[str, Any]]) -> None:
        """
        处理sections列表，递归处理所有section内容，跳过abstract和references
        
        Args:
            sections: section列表
        """
        for section in sections:
            # 跳过abstract和references类型的section
            if section.get('type') in ['abstract', 'references']:
                self.logger.info(f"跳过处理section类型: {section.get('type')}")
                continue
                
            if 'content' in section:
                section['content'] = self._process_content(section['content'])
            
            # 递归处理子section
            if 'children' in section and section['children']:
                self._process_sections(section['children'])
    
    def _process_content(self, content: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        处理content列表，合并和分割文本块
        
        Args:
            content: content列表
            
        Returns:
            List[Dict[str, Any]]: 处理后的content列表
        """
        # 先检查是否需要合并相邻的小文本块
        content = self._merge_small_text_blocks(content)
        
        # 为每个块添加index和part标记
        for idx, item in enumerate(content):
            item['index'] = idx
            # 如果是未分割的块，part为0
            item['part'] = 0
        
        # 然后检查是否需要分割大文本块
        result = []
        for item in content:
            if item['type'] == 'text' and len(item['content']) > self.max_length:
                # 获取原始索引
                original_index = item.get('index', 0)
                
                # 分割大文本块
                if '\n\n' in item['content']:
                    # 使用换行符分割策略
                    elements = item['content'].split('\n\n')
                    split_mode = "delimiter"
                else:
                    # 使用句子分割策略
                    elements = self._split_into_sentences(item['content'])
                    split_mode = "sentence"
                
                # 使用统一的TextTiling算法进行分割
                segments = self._texttiling(elements, split_mode)
                
                # 创建分割后的文本块
                split_blocks = []
                for i, segment_text in enumerate(segments):
                    new_block = item.copy()
                    new_block['content'] = segment_text
                    new_block['index'] = original_index
                    new_block['part'] = i
                    split_blocks.append(new_block)
                
                result.extend(split_blocks)
            else:
                result.append(item)
        
        return result
    
    def _merge_small_text_blocks(self, content: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        合并相邻的小文本块，直到遇到非文本块或满足最小长度的文本块
        
        Args:
            content: content列表
            
        Returns:
            List[Dict[str, Any]]: 处理后的content列表
        """
        if not content:
            return content
        
        result = []
        current_buffer = None
        
        for item in content:
            if item['type'] == 'text':
                # 处理小文本块的逻辑
                if len(item['content']) < self.min_length:
                    # 小文本块，需要合并
                    if current_buffer is None:
                        # 没有缓冲区，创建一个
                        current_buffer = item.copy()
                    else:
                        # 已有缓冲区，直接合并
                        current_buffer['content'] += "\n\n" + item['content']
                else:
                    # 遇到了满足最小长度的文本块
                    if current_buffer is not None:
                        # 有缓冲区，将当前文本块合并到缓冲区
                        current_buffer['content'] += "\n\n" + item['content']
                        result.append(current_buffer)
                        current_buffer = None
                    else:
                        # 添加当前文本块
                        result.append(item)
            else:
                # 遇到非文本块
                if current_buffer is not None:
                    # 有缓冲区，输出缓冲区内容
                    result.append(current_buffer)
                    current_buffer = None
                # 添加当前非文本块
                result.append(item)
        
        # 处理最后的缓冲区
        if current_buffer is not None:
            result.append(current_buffer)
        
        return result
    
    def _texttiling(self, elements: List[str], split_mode: str = "sentence") -> List[str]:
        """
        通用的TextTiling算法实现
        
        Args:
            elements: 文本元素列表（可以是句子或分隔符分割的部分）
            split_mode: 分割模式，"sentence"或"delimiter"
            
        Returns:
            List[str]: 分段结果文本列表
        """
        # 如果元素数量不足，直接返回合并后的文本
        if len(elements) < self.window_size + 2:
            combined_text = ' '.join(elements) if split_mode == "sentence" else '\n\n'.join(elements)
            return [combined_text]
        
        # 创建文本块（窗口）
        blocks = []
        for i in range(0, len(elements) - self.window_size + 1, self.step_size):
            window = elements[i:i + self.window_size]
            if split_mode == "sentence":
                blocks.append(' '.join(window))
            else:  # delimiter mode
                blocks.append('\n'.join(window))
        
        # 计算每个块的嵌入向量 - 使用统一的EmbeddingModel
        embedding_model = EmbeddingModel.get_instance()
        block_embeddings = [embedding_model.embed_query(block) for block in blocks]
        
        # 计算相邻块之间的相似度                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                       
        similarities = [cosine_similarity([block_embeddings[i]], [block_embeddings[i+1]])[0][0] 
                        for i in range(len(block_embeddings)-1)]
        
        # 计算深度分数
        depth_scores = [0] * len(elements)
        for i in range(1, len(similarities)-1):
            depth = (similarities[i-1] + similarities[i+1] - 2*similarities[i]) / 2
            depth_scores[i+self.window_size//2] = depth
        
        # 计算阈值
        depth_values = [d for d in depth_scores if d > 0]
        if depth_values:
            mean_depth = np.mean(depth_values)
            std_depth = np.std(depth_values)
            threshold = mean_depth + 0.4 * std_depth
        else:
            threshold = 0
        
        # 找出潜在的边界
        potential_boundaries = [i for i, score in enumerate(depth_scores) if score > threshold]
        
        # 找到最优分段
        segments = []
        start = 0
        
        while start < len(elements):
            optimal_boundary = self._find_optimal_boundary(start, elements, potential_boundaries, depth_scores)
            
            if split_mode == "sentence":
                segment_text = ' '.join(elements[start:optimal_boundary+1])
            else:  # delimiter mode
                segment_text = '\n'.join(elements[start:optimal_boundary+1])
            
            segments.append(segment_text)
            start = optimal_boundary + 1
        
        # 处理最后一个段落如果太小
        if segments and len(segments[-1]) < self.min_length and len(segments) > 1:
            last_segment = segments.pop()
            if split_mode == "sentence":
                segments[-1] += " " + last_segment
            else:  # delimiter mode
                segments[-1] += "\n" + last_segment
        
        return segments
    
    def _find_optimal_boundary(self, start: int, elements: List[str], 
                               potential_boundaries: List[int], depth_scores: List[float]) -> int:
        """
        找到最优的段落边界
        
        Args:
            start: 起始位置
            elements: 元素列表（句子或分隔部分）
            potential_boundaries: 潜在边界列表
            depth_scores: 深度分数列表
            
        Returns:
            int: 最优边界的索引
        """
        current_length = 0
        candidate_boundaries = []
        
        for i in range(start, len(elements)):
            current_length += len(elements[i])
            if self.min_length <= current_length <= self.max_length:
                if i in potential_boundaries:
                    candidate_boundaries.append((i, depth_scores[i]))
            if current_length > self.max_length:
                break
        
        if not candidate_boundaries:
            # 找一个长度接近目标的位置
            target_length = (self.min_length + self.max_length) / 2
            return min(range(start, min(len(elements), start + 10)), 
                      key=lambda i: abs(sum(len(e) for e in elements[start:i+1]) - target_length))
        
        # 选择深度分数最高的边界
        best_boundary = max(candidate_boundaries, key=lambda x: x[1])
        return best_boundary[0]
    
    def _split_into_sentences(self, text: str) -> List[str]:
        """
        将文本分割成句子（支持中英文）
        
        Args:
            text: 待分割的文本
            
        Returns:
            List[str]: 句子列表
        """
        # 中英文句子结束标志
        sentence_pattern = re.compile(r'(?<=[。！？?!.;；])')
        sentences = [s.strip() for s in re.split(sentence_pattern, text) if s.strip()]
        
        return sentences