from gpt4all import GPT4All
import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)

class AIService:
    def __init__(self, model_name: Optional[str] = None):
        self.model = None
        # Если модель не указана, используем первую найденную в папке models
        self.model_name = model_name or self._find_available_model()
        self.models_dir = os.path.join(os.path.dirname(__file__), "..", "models")
        
    def _find_available_model(self) -> Optional[str]:
        """Находит доступную модель в папке models"""
        if not os.path.exists(self.models_dir):
            return None
            
        models = [f for f in os.listdir(self.models_dir) if f.endswith('.bin')]
        return models[0] if models else None
        
    def initialize(self) -> bool:
        """Инициализация модели"""
        try:
            if not self.model_name:
                logger.error("Модель не найдена в папке models")
                logger.info("Пожалуйста, скачайте модель с https://gpt4all.io/index.html")
                return False
                
            model_path = os.path.join(self.models_dir, self.model_name)
            if not os.path.exists(model_path):
                logger.error(f"Модель {self.model_name} не найдена по пути {model_path}")
                return False
                
            self.model = GPT4All(model_path)
            logger.info(f"Модель {self.model_name} успешно загружена")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка загрузки модели: {e}")
            return False
    
    def generate_response(self, prompt: str, max_tokens: int = 150, temp: float = 0.7) -> str:
        """Генерация ответа с помощью модели"""
        if not self.model:
            return "Извините, ИИ модель временно недоступна."
        
        try:
            # Формируем промпт для модели
            full_prompt = f"""Ты - полезный ассистент в Telegram-боте. Отвечай кратко и по делу.

Пользователь: {prompt}
Ассистент:"""
            
            # Генерируем ответ
            response = self.model.generate(
                full_prompt, 
                max_tokens=max_tokens,
                temp=temp,
                streaming=False
            )
            
            return response.strip()
        except Exception as e:
            logger.error(f"Ошибка генерации ответа: {e}")
            return "Произошла ошибка при обработке запроса."