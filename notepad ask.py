import os
import sys
import google.generativeai as genai

# Берем ключ из переменной окружения
api_key = os.getenv("GEMINI_API_KEY")
genai.configure(api_key=api_key)

model = genai.GenerativeModel('gemini-1.5-flash')

# Собираем вопрос из аргументов командной строки
prompt = " ".join(sys.argv[1:])

if prompt:
    response = model.generate_content(prompt)
    print(f"\nGemini: \n{response.text}")
else:
    print("Введите вопрос после имени файла!")
    