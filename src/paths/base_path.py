import sys
import os
from pathlib import Path

# --- FÓRMULA MÁGICA DO PYINSTALLER ---
if getattr(sys, 'frozen', False):  # Executável compilado
    BASE_DIR = Path(sys._MEIPASS) / "src"  # Diretório temporário + 'src'
else:  # Ambiente de desenvolvimento
    BASE_DIR = Path(__file__).resolve().parent.parent

# --- DEFINIÇÃO DE PASTAS ---
DATABASE_DIR = BASE_DIR / "database"    
MODULES_DIR = BASE_DIR / "modules"
JSON_DIR = DATABASE_DIR / "json"
SQL_DIR = DATABASE_DIR / "sql"

# --- SISTEMA DE AUTO-CURA (Evita erros de DB e JSON no Executável) ---
os.makedirs(DATABASE_DIR, exist_ok=True)
os.makedirs(JSON_DIR, exist_ok=True)
os.makedirs(SQL_DIR, exist_ok=True)

# --- ARQUIVOS ESPECÍFICOS ---
JSON_COMPRASNET_CONTRATOS = JSON_DIR / "consulta_comprasnet"
CONFIG_FILE = JSON_DIR / "config.json"  
CONTROLE_DADOS = SQL_DIR / "controle_dados.db"

# --- ASSETS ---
ASSETS_DIR = BASE_DIR / "assets"
TEMPLATE_DIR = ASSETS_DIR / "templates"
STYLE_PATH = ASSETS_DIR / "style.css" 
ICONS_DIR = ASSETS_DIR / "icons"