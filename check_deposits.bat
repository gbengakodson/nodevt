@echo off
cd C:\Users\easyf\Crypto_platform
call venv\Scripts\activate
python manage.py check_credits >> deposit_log.txt
echo %date% %time% - Check completed >> deposit_log.txt