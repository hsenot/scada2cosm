:loop
python scada_to_pachube.py
ping -n 300 127.0.0.1 >nul
goto loop