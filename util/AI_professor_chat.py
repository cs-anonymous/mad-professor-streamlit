import logging
import json
import os
from typing import List, Dict, Any, Generator, Tuple
from util.config import LLMClient

AI_CHARACTER_PROMPT_PATH = "prompt/ai_character_prompt_leidian.txt"
AI_EXPLAIN_PROMPT_PATH = "prompt/ai_explain_prompt.txt"
AI_ROUTER_PROMPT_PATH = "prompt/ai_router_prompt.txt"

class AIProfessorChat:
    """
    AI对话助手 - 学术论文智能问答系统
    
    支持多种回答策略：
    - 直接回答
    - 页面内容分析
    - 宏观检索（章节概要）
    - RAG检索（精准段落）
    """
    
    def __init__(self):
        """初始化AI对话助手"""
        self.logger = logging.getLogger(__name__)
        
        # 设置基础路径
        self.base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.output_path = os.path.join(self.base_path, "output")
        
        # 对话历史 (保持最近10条)
        self.conversation_history = []
        
        # 当前论文上下文
        self.current_paper_id = None
        self.current_paper_data = None
        
        # 将实例化改为引用初始化
        self.retriever = None  # 稍后由AI_manager设置
        
        # LLM客户端
        self.llm_client = None
        try:
            self.llm_client = LLMClient()
            self.logger.info("AI对话助手初始化完成")
        except Exception as e:
            self.logger.error(f"初始化AI对话组件失败: {str(e)}")

    def _read_file(self, filepath: str) -> str:
        """读取文件内容"""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return f.read().strip()
        except Exception as e:
            self.logger.warning(f"读取文件 {filepath} 失败: {str(e)}")
            return ""
    
    def set_paper_context(self, paper_id: str, paper_data: Dict[str, Any]) -> bool:
        """设置当前论文上下文
        
        Args:
            paper_id: 论文ID
            paper_data: 论文数据字典
            
        Returns:
            bool: 成功返回True，失败返回False
        """
        try:
            self.current_paper_id = paper_id
            self.current_paper_data = paper_data
            self.logger.info(f"已设置论文上下文: {paper_id}")
            return True
        except Exception as e:
            self.logger.error(f"设置论文上下文失败: {str(e)}")
            return False
    
    def process_query_stream(self, query: str, visible_content: str = None) -> Generator[Tuple[str, str, Dict], None, None]:
        """流式处理用户查询并生成回答，按句子返回
        
        Args:
            query: 用户查询文本
            visible_content: 当前可见的页面内容
            
        Yields:
            Tuple[str, str, Dict]: (生成的句子, 情绪, 滚动定位信息)
            
        Returns:
            Generator: 句子生成器
        """
        try:
            if not self.llm_client:
                yield "AI服务尚未初始化，请稍后再试。", None, None
                return

            print(f"\n==== 用户查询 ====\n{query}")

            # 1. 检查是否需要添加用户问题到对话历史
            should_add_query = True
            if self.conversation_history and len(self.conversation_history) > 0:
                last_message = self.conversation_history[-1]
                if last_message["role"] == "user" and last_message["content"] == query:
                    # 问题已存在于历史记录的最后一条，不需要重复添加
                    should_add_query = False
                    self.logger.info("检测到重复问题，跳过添加到历史记录")
            
            # 只有在需要时才添加问题到对话历史
            if should_add_query:
                self.conversation_history.append({"role": "user", "content": query})
            
            # 保持对话历史在合理长度
            if len(self.conversation_history) > 10:
                self.conversation_history = self.conversation_history[-10:]
                
            # 2. 决策过程 - 调用LLM进行决策
            decision = self._make_decision(query)
            self.logger.info(f"决策结果: {decision}")
            print(f"\n==== 决策结果 ====\n{json.dumps(decision, ensure_ascii=False, indent=2)}")
            
            # 3. 根据决策选择策略
            emotion = decision.get('emotion', 'neutral')
            function_name = decision.get('function', 'direct_answer')
            optimized_query = decision.get('query', query)  # 获取优化后的查询
            
            # 4. 根据策略执行不同的处理
            context_info = ""
            scroll_info = None  # 初始化滚动信息
            
            if function_name == 'direct_answer':
                # 直接回答，不需要额外信息
                print("\n==== 直接回答模式 ====\n无需检索上下文")
                pass
            
            elif function_name == 'page_content_analysis':
                # 分析当前页面内容
                if visible_content:
                    context_info = f"以下是页面当前显示的内容:\n\n{visible_content}"
                    print(f"\n==== 页面内容分析 ====\n{context_info}")
            
            elif function_name == 'macro_retrieval':
                # 宏观检索 - 获取章节概要
                if self.current_paper_data:
                    context_info = self._get_macro_context(optimized_query)  # 使用优化查询
            
            elif function_name == 'rag_retrieval':
                # RAG检索 - 获取相关段落
                if self.current_paper_id:
                    context_info, scroll_info = self._get_rag_context(optimized_query)  # 使用优化查询
            
            else:
                # 未知策略，使用直接回答
                self.logger.warning(f"未知的回答策略: {function_name}，使用直接回答")
            
            # 5. 准备最终查询消息，传递原始查询、优化查询和回答策略
            final_messages = self._prepare_final_messages(
                query=query,
                context_info=context_info,
                emotion=emotion,
                optimized_query=optimized_query,  # 传递优化后的查询
                function_name=function_name  # 传递回答策略
            )
            
            print(f"\n==== 最终发送给LLM的消息 ====")
            for i, msg in enumerate(final_messages):
                print(f"消息 {i+1} - 角色: {msg['role']}")
                print(f"内容: {msg['content']}\n")
            
            # 6. 调用LLM获取流式回答
            response_generator = self.llm_client.chat_stream_by_sentence(
                messages=final_messages,
                temperature=0.7
            )
            
            # 7. 收集完整响应以添加到历史记录
            full_response = ""
            
            # 8. 流式返回结果，第一个句子附带滚动信息
            first_sentence = True
            for sentence in response_generator:
                full_response += sentence
                if first_sentence:
                    yield sentence, emotion, scroll_info  # 添加情绪参数
                    first_sentence = False
                else:
                    yield sentence, emotion, None  # 添加情绪参数
            
            # 9. 记录AI回答到对话历史
            self.conversation_history.append({"role": "assistant", "content": full_response})
            
            print(f"\n==== LLM完整响应 ====\n{full_response}")
            
        except Exception as e:
            error_msg = f"流式处理查询失败: {str(e)}"
            self.logger.error(error_msg)
            yield f"抱歉，处理您的问题时出现错误: {str(e)}", None, None
    
    def record_assistant_response(self, response):
        """记录AI助手的回应到对话历史
        
        Args:
            response: AI生成的回答
        """
        # 记录AI回答到对话历史
        self.conversation_history.append({"role": "assistant", "content": response})
    
    def _validate_decision(self, decision_data: Dict[str, str]) -> bool:
        """验证决策结果是否符合要求
        
        Args:
            decision_data: 决策数据字典
            
        Returns:
            bool: 验证通过返回True，否则返回False
        """
        # 检查必要字段
        required_fields = ["emotion", "function", "query"]
        if not all(field in decision_data for field in required_fields):
            self.logger.warning("决策数据缺少必要字段")
            return False
        
        # 确保emotion在有效范围内
        valid_emotions = ["happy", "sad", "angry", "fearful", "disgusted", "surprised", "neutral"]
        if decision_data["emotion"] not in valid_emotions:
            self.logger.warning(f"无效的情绪类型: {decision_data['emotion']}")
            return False
            
        # 确保function在有效范围内
        valid_functions = ["direct_answer", "page_content_analysis", "macro_retrieval", "rag_retrieval"]
        if decision_data["function"] not in valid_functions:
            self.logger.warning(f"无效的功能类型: {decision_data['function']}")
            return False
        
        return True

    def _make_decision(self, query: str) -> Dict[str, str]:
        """决定如何回答用户的问题
        
        Args:
            query: 用户查询
                
        Returns:
            Dict[str, str]: 包含emotion, function, query的决策字典
        """
        # 默认决策结果
        default_decision = {
            "emotion": "neutral",
            "function": "direct_answer",
            "query": query  # 默认使用原始查询
        }
        
        try:
            # 1. 读取并准备决策提示词
            router_prompt = self._read_file(AI_ROUTER_PROMPT_PATH)
            
            # 确定当前论文状态
            has_paper_loaded = self.current_paper_id is not None and self.current_paper_data is not None
            paper_status = "有论文加载" if has_paper_loaded else "无论文加载"
            
            # 获取当前论文标题（如果有）
            paper_title = "无论文"
            if has_paper_loaded:
                paper_title = self.current_paper_data.get('translated_title', '') or self.current_paper_data.get('title', '')
                paper_title = f"当前论文标题: {paper_title}"
            
            # 准备对话历史格式 - 不包括最新的用户查询
            formatted_history = ""
            if len(self.conversation_history) > 1:  # 确保有足够的历史记录
                # 只取最近的历史记录（不包括最新的用户查询）
                recent_history = self.conversation_history[:-1][-4:]  # 最多取4条历史记录(不包括最新的)
                history_items = []
                for msg in recent_history:
                    role = "用户" if msg["role"] == "user" else "暴躁教授"
                    content = msg["content"]
                    history_items.append(f"{role}: {content}")
                formatted_history = "\n".join(history_items)
            
            # 将论文状态、论文标题和对话历史添加到提示中
            decision_prompt = router_prompt.format(
                query=query, 
                paper_status=paper_status,
                paper_title=paper_title,
                conversation_history=formatted_history
            )
            
            print(f"\n==== 决策提示 ====\n{decision_prompt}")
            
            # 2. 准备调用LLM的消息
            messages = [{"role": "user", "content": decision_prompt}]
            
            # 3. 最多尝试两次
            import re
            decision_data = None
            
            for attempt in range(2):
                self.logger.info(f"决策请求尝试 {attempt+1}/2")
                
                # 调用LLM进行决策
                decision_response = self.llm_client.chat(
                    messages=messages,
                    temperature=0.7,
                    stream=False
                )
                
                print(f"\n==== 决策LLM响应 (尝试 {attempt+1}) ====\n{decision_response}")
                
                # 使用正则表达式匹配JSON结构
                json_match = re.search(r'\{.*\}', decision_response, re.DOTALL)
                if not json_match:
                    self.logger.warning("无法从响应中提取JSON，将重试")
                    continue
                    
                try:
                    # 解析提取的JSON
                    decision_data = json.loads(json_match.group(0))
                    
                    # 验证决策数据
                    if self._validate_decision(decision_data):
                        # 验证通过，跳出循环
                        break
                    else:
                        self.logger.warning("决策验证失败，将重试")
                except json.JSONDecodeError:
                    self.logger.warning("JSON解析失败，将重试")
            
            # 4. 如果无论文加载，强制使用direct_answer
            if not has_paper_loaded and decision_data and self._validate_decision(decision_data):
                decision_data["function"] = "direct_answer"
                self.logger.info("无论文加载，强制使用direct_answer策略")
            
            # 5. 返回决策结果：如果decision_data有效则使用它，否则使用默认值
            if decision_data and self._validate_decision(decision_data):
                return {
                    "emotion": decision_data["emotion"],
                    "function": decision_data["function"],
                    "query": decision_data["query"]
                }
            else:
                self.logger.warning("所有决策尝试均失败，使用默认决策")
                return default_decision
                
        except Exception as e:
            self.logger.error(f"决策过程失败: {str(e)}")
            return default_decision
    
    def _get_macro_context(self, query: str) -> str:
        """获取宏观上下文 - 从章节概要中提取
        
        提取内容:
        - 论文总标题(翻译或原始)
        - 论文总摘要(如果存在)
        - 第一级章节的标题和摘要(不递归处理子章节)
        
        Args:
            query: 检索查询
            
        Returns:
            str: 宏观上下文信息
        """
        try:
            if not self.current_paper_data:
                return ""
                    
            # 提取章节标题和摘要
            context_parts = []
            
            # 添加文档标题
            doc_title = self.current_paper_data.get('translated_title', '') or self.current_paper_data.get('title', '')
            if doc_title:
                context_parts.append(f"# {doc_title}")
            
            # 添加论文总摘要(如果存在)
            if 'summary' in self.current_paper_data and self.current_paper_data['summary']:
                context_parts.append(f"## 总摘要\n{self.current_paper_data['summary']}")
            
            # 添加第一级章节标题和摘要(不递归)
            if 'sections' in self.current_paper_data and self.current_paper_data['sections']:
                context_parts.append("## 章节概要")
                for section in self.current_paper_data['sections']:
                    # 提取章节标题(优先使用翻译标题)
                    section_title = section.get('translated_title', '') or section.get('title', '')
                    
                    # 提取章节摘要
                    section_summary = section.get('summary', '')
                    
                    if section_title:
                        # 添加章节标题和摘要
                        section_text = f"### {section_title}"
                        if section_summary:
                            section_text += f"\n{section_summary}"
                        
                        context_parts.append(section_text)
            
            # 组合所有上下文
            if context_parts:
                context_result = "\n\n".join(context_parts)
                print(f"\n==== 宏观检索结果 ====\n{context_result}")
                return context_result
            else:
                print("\n==== 宏观检索结果为空 ====")
                return ""
                    
        except Exception as e:
            self.logger.error(f"获取宏观上下文失败: {str(e)}")
            return ""
    
    def _get_rag_context(self, query: str) -> Tuple[str, Dict]:
        """从RAG检索器获取相关上下文和滚动定位信息"""
        try:
            if not self.current_paper_id or not query:
                return "", None
            
            print(f"\n==== RAG检索查询 ====\n{query}")
            
            # 添加检查 - 确保检索器存在且已加载完成
            if not self.retriever:
                self.logger.warning("RAG检索器未初始化，无法执行检索")
                return "", None
                
            # 检查检索器是否就绪
            if not self.retriever.is_ready():
                self.logger.warning("RAG检索器尚未加载完成，无法执行检索")
                return "", None
                
            # 使用RAG检索器获取结构化相关内容和滚动信息
            context, scroll_info = self.retriever.retrieve_with_context(
                query=query,
                paper_id=self.current_paper_id,
                top_k=5
            )
            
            print(f"\n==== RAG检索结果 ====\n{context}")
            
            return context, scroll_info
                
        except Exception as e:
            self.logger.error(f"RAG检索失败: {str(e)}")
            return "", None
    
    def _prepare_final_messages(self, query: str, context_info: str, emotion: str, optimized_query: str = None, function_name: str = None) -> List[Dict[str, str]]:
        """准备最终发送给LLM的消息列表
        
        Args:
            query: 原始用户查询
            context_info: 上下文信息
            emotion: 情绪类型
            optimized_query: 优化后的查询
            function_name: 回答策略
            
        Returns:
            List[Dict[str, str]]: 消息列表
        """
        messages = []
        
        # 读取角色提示词和解释提示词
        character_prompt = self._read_file(AI_CHARACTER_PROMPT_PATH)
        explain_prompt = self._read_file(AI_EXPLAIN_PROMPT_PATH)
        
        # 添加论文标题到系统提示(如果有)
        title = ""
        if self.current_paper_data:
            title = self.current_paper_data.get('translated_title', '') or self.current_paper_data.get('title', '')
        else:
            title = "无论文"

        explain_prompt = explain_prompt.format(title=title)
        
        # 系统提示 - 使用回车拼接提示词
        system_message = f"{character_prompt}\n{explain_prompt}"
        
        messages.append({"role": "system", "content": system_message})
        
        # 添加对话历史（不包括最新的用户查询）
        if len(self.conversation_history) > 1:
            messages.extend(self.conversation_history[:-1])  
        
        # 构建用户查询 - 包含原始查询和优化查询
        final_query = f"当前用户消息：{query}\n\n你的回答情绪应该是：{emotion}"
        
        # 如果有上下文信息，根据function_name添加对应的信息类型说明
        if context_info:
            context_type = "参考信息"
            if function_name == "page_content_analysis":
                context_type = "当前页面内容"
            elif function_name == "macro_retrieval":
                context_type = "论文概要"
            elif function_name == "rag_retrieval":
                context_type = "相关论文段落"
        
            final_query = f"{final_query}\n\n{context_type}:\n{context_info}"
        
        final_query += f"{final_query}\n\n输出回复的话："
        # 添加最终用户查询
        messages.append({"role": "user", "content": final_query})
        
        return messages