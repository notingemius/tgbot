import os
import logging
from config import MODEL_NAME, MODELS_DIR

logger = logging.getLogger(__name__)

class AIService:
    def __init__(self):
        self.model = None
        
    def initialize(self) -> bool:
        """Инициализация модели через GPT4All класс (автоматическое скачивание)"""
        try:
            logger.info(f"Загружаем модель: {MODEL_NAME}")
            
            # Импортируем GPT4All
            from gpt4all import GPT4All
            
            # Создаем папку для моделей, если ее нет
            os.makedirs(MODELS_DIR, exist_ok=True)
            
            # Загружаем модель через класс GPT4All - он автоматически скачает при первом использовании
            # Указываем путь для сохранения модели в нашу папку models
            self.model = GPT4All(model_name=MODEL_NAME, model_path=MODELS_DIR)
            logger.info(f"Модель {MODEL_NAME} успешно загружена")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка загрузки модели: {e}")
            return False
    
    def generate_response(self, prompt: str) -> str:
        """Генерация ответа с помощью модели"""
        if not self.model:
            return "Извините, ИИ модель временно недоступна."
        
        try:
            # Простой вызов модели
            response = self.model.generate(prompt, max_tokens=100)
            return response.strip()
        except Exception as e:
            logger.error(f"Ошибка генерации ответа: {e}")
            return "Произошла ошибка при обработке запроса."