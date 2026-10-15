from opssentinel.config import settings
from opssentinel.llm import get_llm

print(f"Provider: {settings.llm_provider}")
print(f"Model:    {settings.active_model}")

llm = get_llm()
response = llm.invoke("Reply with exactly one word: ready")
print(f"Response: {response.content}")