import os
import json
from langchain_anthropic import ChatAnthropic
from langchain_deepseek import ChatDeepSeek
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_groq import ChatGroq
from langchain_openai import ChatOpenAI
from langchain_community.chat_models.moonshot import MoonshotChat
from openai import OpenAI  # 更新 OpenAI 导入方式
from enum import Enum
from pydantic import BaseModel
from typing import Tuple


class ModelProvider(str, Enum):
    """Enum for supported LLM providers"""
    ANTHROPIC = "Anthropic"
    DEEPSEEK = "DeepSeek"
    GEMINI = "Gemini"
    GROQ = "Groq"
    OPENAI = "OpenAI"
    MOONSHOT = "Moonshot"


class LLMModel(BaseModel):
    """Represents an LLM model configuration"""
    display_name: str
    model_name: str
    provider: ModelProvider

    def to_choice_tuple(self) -> Tuple[str, str, str]:
        """Convert to format needed for questionary choices"""
        return (self.display_name, self.model_name, self.provider.value)
    
    def has_json_mode(self) -> bool:
        """Check if the model supports JSON mode"""
        return not self.is_deepseek() and not self.is_gemini()
    
    def is_deepseek(self) -> bool:
        """Check if the model is a DeepSeek model"""
        return self.model_name.startswith("deepseek")
    
    def is_gemini(self) -> bool:
        """Check if the model is a Gemini model"""
        return self.model_name.startswith("gemini")
    
    def is_moonshot(self) -> bool:
        """Check if the model is a Moonshot model"""
        return self.model_name.startswith("moonshot")

class MoonshotChatSelf(object):
    # self defined from langchain_community.chat_models.moonshot import MoonshotChat
    def __init__(self, model: str, api_key: str):
        self.client = {
            "env_model": model,
            "env_api_key": api_key,
            "init_func": lambda key: OpenAI(api_key=key, base_url="https://api.moonshot.cn/v1"),
            "name": "Moonshot",
        }
        self.output_schema = None
        self.response_format = {"type": "json_object"}
    
    def with_structured_output(self, output_schema: BaseModel, method="json_mode"):
        """
        mock with_structured_output
        设置模型的输出模式为结构化输出模式，并指定输出模式的方法。
        Args:
            output_schema (Any): 输出模式的模式定义。
            method (str): 输出模式的方法，默认为 "json_mode"。
        Returns:
            MoonshotChat: 配置好的 MoonshotChat 实例。
        """
        if output_schema:
            self.output_schema = output_schema
        if method == "json_mode":
            self.response_format = {"type": "json_object"}
            
        return self
    
    def invoke(self, messages):
        """
        mock invoke
        调用模型的聊天接口。
        Args:
            messages (List[Dict[str, str]]): 聊天消息列表，每个消息包含角色和内容。
        Returns:
            str: 模型的响应内容。
        """
        try:
            if self.client is None:
                raise ValueError("客户端未初始化")
            _client_call = self.client["init_func"](self.client["env_api_key"])
            _messages = messages.to_messages()
            messages_trans = []
            for msg in _messages:
                temp_msg = {}
                temp_msg["role"] = msg.type if msg.type == "system" else "user" # change human to user
                temp_msg["content"] = msg.content
                messages_trans.append(temp_msg) 
            
            assert len(messages_trans) == len(_messages), "转换后的消息数量与原始消息数量不一致"
            
            # 使用 OpenAI API
            response = _client_call.chat.completions.create(
                model=self.client["env_model"],
                messages=messages_trans,
                temperature=0.3,  # Kimi 特定参数
                response_format=self.response_format,
            )
            content = response.choices[0].message.content
            
            # Pydantic模型校验
            if self.output_schema is None:
                return content
            else:
                validated = self.output_schema(**json.loads(content))
                return validated            
        except Exception as e:
            raise e


# Define available models
AVAILABLE_MODELS = [
    LLMModel(
        display_name="[anthropic] claude-3.5-haiku",
        model_name="claude-3-5-haiku-latest",
        provider=ModelProvider.ANTHROPIC
    ),
    LLMModel(
        display_name="[anthropic] claude-3.5-sonnet",
        model_name="claude-3-5-sonnet-latest",
        provider=ModelProvider.ANTHROPIC
    ),
    LLMModel(
        display_name="[anthropic] claude-3.7-sonnet",
        model_name="claude-3-7-sonnet-latest",
        provider=ModelProvider.ANTHROPIC
    ),
    LLMModel(
        display_name="[deepseek] deepseek-r1",
        model_name="deepseek-reasoner",
        provider=ModelProvider.DEEPSEEK
    ),
    LLMModel(
        display_name="[deepseek] deepseek-v3",
        model_name="deepseek-chat",
        provider=ModelProvider.DEEPSEEK
    ),
    LLMModel(
        display_name="[gemini] gemini-2.0-flash",
        model_name="gemini-2.0-flash",
        provider=ModelProvider.GEMINI
    ),
    LLMModel(
        display_name="[gemini] gemini-2.5-pro",
        model_name="gemini-2.5-pro-exp-03-25",
        provider=ModelProvider.GEMINI
    ),
    LLMModel(
        display_name="[groq] llama-3.3 70b",
        model_name="llama-3.3-70b-versatile",
        provider=ModelProvider.GROQ
    ),
    LLMModel(
        display_name="[groq] llama-4-scout",
        model_name="meta-llama/llama-4-scout-17b-16e-instruct",
        provider=ModelProvider.GROQ
    ),
    LLMModel(
        display_name="[openai] gpt-4.5",
        model_name="gpt-4.5-preview",
        provider=ModelProvider.OPENAI
    ),
    LLMModel(
        display_name="[openai] gpt-4o",
        model_name="gpt-4o",
        provider=ModelProvider.OPENAI
    ),
    LLMModel(
        display_name="[openai] o1",
        model_name="o1",
        provider=ModelProvider.OPENAI
    ),
    LLMModel(
        display_name="[openai] o3-mini",
        model_name="o3-mini",
        provider=ModelProvider.OPENAI
    ),
    LLMModel(
        display_name="[kimi] moonshot-v1-8k",
        model_name="moonshot-v1-8k",
        provider=ModelProvider.MOONSHOT
    ),
]

# Create LLM_ORDER in the format expected by the UI
LLM_ORDER = [model.to_choice_tuple() for model in AVAILABLE_MODELS]

def get_model_info(model_name: str) -> LLMModel | None:
    """Get model information by model_name"""
    return next((model for model in AVAILABLE_MODELS if model.model_name == model_name), None)

def get_model(model_name: str, model_provider: ModelProvider) -> ChatOpenAI | ChatGroq | None:
    if model_provider == ModelProvider.GROQ:
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            # Print error to console
            print(f"API Key Error: Please make sure GROQ_API_KEY is set in your .env file.")
            raise ValueError("Groq API key not found.  Please make sure GROQ_API_KEY is set in your .env file.")
        return ChatGroq(model=model_name, api_key=api_key)
    elif model_provider == ModelProvider.OPENAI:
        # Get and validate API key
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            # Print error to console
            print(f"API Key Error: Please make sure OPENAI_API_KEY is set in your .env file.")
            raise ValueError("OpenAI API key not found.  Please make sure OPENAI_API_KEY is set in your .env file.")
        return ChatOpenAI(model=model_name, api_key=api_key)
    elif model_provider == ModelProvider.ANTHROPIC:
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            print(f"API Key Error: Please make sure ANTHROPIC_API_KEY is set in your .env file.")
            raise ValueError("Anthropic API key not found.  Please make sure ANTHROPIC_API_KEY is set in your .env file.")
        return ChatAnthropic(model=model_name, api_key=api_key)
    elif model_provider == ModelProvider.DEEPSEEK:
        api_key = os.getenv("DEEPSEEK_API_KEY")
        if not api_key:
            print(f"API Key Error: Please make sure DEEPSEEK_API_KEY is set in your .env file.")
            raise ValueError("DeepSeek API key not found.  Please make sure DEEPSEEK_API_KEY is set in your .env file.")
        return ChatDeepSeek(model=model_name, api_key=api_key)
    elif model_provider == ModelProvider.GEMINI:
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            print(f"API Key Error: Please make sure GOOGLE_API_KEY is set in your .env file.")
            raise ValueError("Google API key not found.  Please make sure GOOGLE_API_KEY is set in your .env file.")
        return ChatGoogleGenerativeAI(model=model_name, api_key=api_key)
    elif model_provider == ModelProvider.MOONSHOT:
        # https://python.langchain.com/api_reference/community/chat_models/langchain_community.chat_models.moonshot.MoonshotChat.html
        api_key = os.getenv("MOONSHOT_API_KEY")
        if not api_key:
            print(f"API Key Error: Please make sure MOONSHOT_API_KEY is set in your.env file.")
            raise ValueError("Moonshot API key not found.  Please make sure MOONSHOT_API_KEY is set in your.env file.")
        return MoonshotChatSelf(model=model_name, api_key=api_key)