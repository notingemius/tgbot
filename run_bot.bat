@echo off
call C:\Windows\System32\activate.bat llm    :: или путь к твоему conda
cd /d D:\telegram_reminder_bot
set OMP_NUM_THREADS=4
set TELEGRAM_TOKEN=7941127926:AAH...
python main.py
