import PyInstaller.__main__
import shutil
import os

print("=== INICIANDO SISTEMA DE COMPILAÇÃO LICITAÇÃO 360 ===")

# 1. Limpeza de builds anteriores
for pasta in ['build', 'dist']:
    if os.path.exists(pasta):
        shutil.rmtree(pasta)
        print(f" - Pasta '{pasta}' removida.")

for arquivo in ['Licitacao360_Pro.spec', 'Licitacao360.spec']:
    if os.path.exists(arquivo):
        os.remove(arquivo)
        print(f" - Arquivo '{arquivo}' removido.")

print("\nEmpacotando com coleta total de dependências...")

# 2. Compilação com injeção explícita de pacotes pesados
PyInstaller.__main__.run([
    'src/main.py',
    '--noconfirm',
    # DICA: Use '--console' durante os testes. Se houver erro, ele será impresso no terminal preto.
    # Assim que estiver tudo validado, volte para '--windowed'.
    '--console',
    '--name=Licitacao360_Pro',
    '--icon=src/assets/icons/icon3.ico',
    '--paths=src',
    f'--add-data=src/assets{os.pathsep}src/assets',
    f'--add-data=src/database{os.pathsep}src/database',
    
    # Coleta completa de bibliotecas complexas de PDF e dados
    '--collect-all=pdfplumber',
    '--collect-all=pdfminer',
    '--collect-all=fitz',
    '--collect-all=openpyxl',
    '--collect-all=pandas',
    
    # Submódulos essenciais do PyQt6
    '--hidden-import=PyQt6.QtCore',
    '--hidden-import=PyQt6.QtGui',
    '--hidden-import=PyQt6.QtWidgets',
    '--hidden-import=PyQt6.QtSql',
])

print("\n=== COMPILAÇÃO FINALIZADA COM SUCESSO! ===")