import PyInstaller.__main__
import shutil
import os

print("=== INICIANDO SISTEMA DE COMPILAÇÃO LICITAÇÃO 360 ===")

# 1. Limpeza Profunda (Garante que o Windows não usa cache antigo)
pastas_lixo = ['build', 'dist']
arquivos_lixo = ['Licitacao360_Pro.spec', 'Licitacao360.spec']

print("\n[1/3] Limpando compilações antigas...")
for pasta in pastas_lixo:
    if os.path.exists(pasta):
        shutil.rmtree(pasta)
        print(f" - Pasta '{pasta}' apagada.")

for arquivo in arquivos_lixo:
    if os.path.exists(arquivo):
        os.remove(arquivo)
        print(f" - Arquivo '{arquivo}' apagado.")

# 2. Configuração dos Caminhos (Usa os.pathsep para garantir compatibilidade)
separador = os.path.join("src", "assets") + os.pathsep + os.path.join("src", "assets")
separador_db = os.path.join("src", "database") + os.pathsep + os.path.join("src", "database")

print("\n[2/3] Empacotando o projeto (Isto pode demorar alguns minutos)...")

# 3. Execução do PyInstaller internamente
PyInstaller.__main__.run([
    'src/main.py',                               # Ficheiro principal
    '--noconfirm',                               # Substitui sem perguntar
    '--windowed',                                # Esconde o terminal preto (CMD)
    '--name=Licitacao360',                   # Nome do ficheiro .exe final
    '--icon=src/assets/icons/icon3.ico',         # Ícone do programa
    f'--add-data=src/assets{os.pathsep}src/assets',       # Injeta a pasta de imagens
    f'--add-data=src/database{os.pathsep}src/database',   # Injeta a base de dados
])

print("\n[3/3] COMPILAÇÃO CONCLUÍDA COM SUCESSO!")
print("Verifique a pasta 'dist/Licitacao360_Pro' para encontrar o seu executável.")