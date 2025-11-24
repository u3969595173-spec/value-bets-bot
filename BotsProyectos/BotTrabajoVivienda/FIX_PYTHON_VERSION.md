# 🚨 PROBLEMA: Python 3.14 incompatible

## ❌ Error actual:
```
RuntimeError: There is no current event loop in thread 'MainThread'
```

## ✅ SOLUCIÓN: Usar Python 3.11

### Opción 1: Descargar Python 3.11

1. Descarga Python 3.11.9 desde: https://www.python.org/downloads/release/python-3119/
2. Instala (marca "Add to PATH")
3. Ejecuta:

```powershell
cd C:\BotsProyectos\BotTrabajoVivienda
py -3.11 -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
python main.py
```

### Opción 2: Usar pyenv-win (recomendado)

```powershell
# Instalar pyenv-win
Invoke-WebRequest -UseBasicParsing -Uri "https://raw.githubusercontent.com/pyenv-win/pyenv-win/master/pyenv-win/install-pyenv-win.ps1" -OutFile "./install-pyenv-win.ps1"; &"./install-pyenv-win.ps1"

# Instalar Python 3.11
pyenv install 3.11.9
pyenv local 3.11.9

# Crear venv con Python 3.11
cd C:\BotsProyectos\BotTrabajoVivienda
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
python main.py
```

### Opción 3: Actualizar python-telegram-bot (cuando soporten 3.14)

Actualizar `requirements.txt`:
```
python-telegram-bot>=22.0
```

Pero aún no existe versión 22.0 compatible con Python 3.14.

---

## 🎯 ¿Qué hacer ahora?

**RECOMENDADO:** Descarga Python 3.11.9 e instálalo, luego ejecuta los comandos de la Opción 1.

Una vez funcione, verás:
```
2025-11-24 00:XX:XX - __main__ - INFO - Bot iniciado correctamente ✅
```

Y podrás probar el bot en Telegram buscándolo por su nombre.
