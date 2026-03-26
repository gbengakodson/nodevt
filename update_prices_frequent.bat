@echo off
cd C:\Users\easyf\Crypto_platform
call venv\Scripts\activate
python manage.py update_prices >> price_log.txt
echo %date% %time% - Prices updated >> price_log.txt