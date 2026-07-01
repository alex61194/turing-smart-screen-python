@echo off
cd /d "C:\Users\Alex\Desktop\turing-original"
echo Starting main.py at %date% %time% >> run_log.txt
"C:\Users\Alex\AppData\Local\Programs\Python\Python313\python.exe" main.py >> run_log.txt 2>&1
echo main.py exited with code %errorlevel% at %date% %time% >> run_log.txt
