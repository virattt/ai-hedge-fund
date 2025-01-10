import pytest
from src.config.models import get_chat_model
from langchain_openai import ChatOpenAI
from langchain_groq import ChatGroq
from langchain.schema import HumanMessage




@pytest.mark.unit
def test_default_openai_model():
    """Test that default OpenAI model (gpt-4) is returned when no parameters are specified"""
    model = get_chat_model()
    assert isinstance(model, ChatOpenAI)
    assert model.model_name == "gpt-4"
    assert model.temperature == 0.7

@pytest.mark.unit
def test_custom_openai_model():
    """Test that specified OpenAI model is returned"""
    model = get_chat_model(provider="openai", model="gpt-3.5-turbo")
    assert isinstance(model, ChatOpenAI)
    assert model.model_name == "gpt-3.5-turbo"
    assert model.temperature == 0.7

@pytest.mark.unit
def test_default_groq_model():
    """Test that default Groq model (mixtral-8x7b-32768) is returned"""
    model = get_chat_model(provider="groq")
    assert isinstance(model, ChatGroq)
    assert model.model_name == "mixtral-8x7b-32768"
    assert model.temperature == 0.7
    assert model.max_tokens == 1024

@pytest.mark.unit
def test_custom_groq_models():
    """Test that specified Groq models are returned"""
    test_models = ["llama2-70b-4096", "gemma-7b-it", "mixtral-8x7b-32768"]
    
    for test_model in test_models:
        model = get_chat_model(provider="groq", model=test_model)
        assert isinstance(model, ChatGroq)
        assert model.model_name == test_model
        assert model.temperature == 0.7
        assert model.max_tokens == 1024

@pytest.mark.unit
def test_invalid_provider():
    """Test that invalid provider raises ValueError"""
    with pytest.raises(ValueError):
        get_chat_model(provider="invalid_provider")



@pytest.mark.integration
def test_openai_chat_completion():
    """Test that OpenAI model can generate a response"""
    from openai import RateLimitError
    
    model = get_chat_model(provider="openai", model="gpt-3.5-turbo")
    messages = [HumanMessage(content="Say 'hello' and nothing else")]
    
    try:
        response = model.invoke(messages)
        assert response.content.lower().strip() == "hello"
    except RateLimitError:
        pytest.skip("OpenAI rate limit reached")

@pytest.mark.integration
def test_groq_chat_completion():
    """Test that Groq model can generate a response"""
    model = get_chat_model(provider="groq", model="mixtral-8x7b-32768")
    messages = [HumanMessage(content="Say 'hello' and nothing else")]
    response = model.invoke(messages)
    
    assert "hello" in response.content.lower().strip()

@pytest.mark.integration
def test_openai_streaming():
    """Test that OpenAI model can stream responses"""
    from openai import RateLimitError
    
    model = get_chat_model(provider="openai", model="gpt-3.5-turbo")
    messages = [HumanMessage(content="Count from 1 to 3")]
    
    try:
        response_chunks = []
        for chunk in model.stream(messages):
            response_chunks.append(chunk.content)
        
        full_response = ''.join(response_chunks)
        assert all(str(num) in full_response for num in range(1, 4))
    except RateLimitError:
        pytest.skip("OpenAI rate limit reached")

@pytest.mark.integration
def test_groq_streaming():
    """Test that Groq model can stream responses"""
    model = get_chat_model(provider="groq", model="mixtral-8x7b-32768")
    messages = [HumanMessage(content="Count from 1 to 3")]
    
    response_chunks = []
    for chunk in model.stream(messages):
        response_chunks.append(chunk.content)
    
    full_response = ''.join(response_chunks)
    assert all(str(num) in full_response for num in range(1, 4))