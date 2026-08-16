@echo off
cd /d "C:\Users\KGP\Desktop\Cursos Data y FWSD\Curso Ciencia y tratamiento de Datos\2.-PR Qualitat aire bcn"
call .venv\Scripts\activate.bat
python src\run_pipeline.py >> pipeline_log.txt 2>&1