import sys
import os
import subprocess
from pathlib import Path
from PyQt6.QtWidgets import *
from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QFont, QDesktopServices, QPixmap, QIcon

# Importação do caminho oficial dos ícones
from paths import ICONS_DIR 

class InicioWidget(QWidget):
    def __init__(self, icons, parent=None):
        super().__init__(parent)
        self.icons = icons
        self.setup_ui()

    def setup_ui(self):
        # Layout principal da tela inicial
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(50, 50, 50, 50)
        self.main_layout.setSpacing(20)

        # ==========================================
        # 1. CABEÇALHO (LOGO E TÍTULOS)
        # ==========================================
        header_layout = QHBoxLayout()
        header_layout.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        # Adicionando a Logo com efeito "Badge" (Distintivo adaptável a temas claros e escuros)
        self.lbl_logo = QLabel()
        self.lbl_logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        caminho_icone = ICONS_DIR / "icon3.ico"
        if caminho_icone.exists():
            icone = QIcon(str(caminho_icone))
            pixmap = icone.pixmap(90, 90)  # Tamanho da logo
            self.lbl_logo.setPixmap(pixmap)
            
            # --- Estilo do "Badge" para destacar a logo ---
            self.lbl_logo.setStyleSheet("""
                QLabel {
                    background-color: #F0F2F5; /* Fundo claro constante */
                    border-radius: 16px;       /* Bordas modernas arredondadas */
                    padding: 12px;             /* Respiro interno */
                    border: 1px solid #2D2E3E; /* Borda sutil para não flutuar solto */
                }
            """)
        else:
            print(f"Aviso interno: Logo não encontrada no caminho {caminho_icone}")
        
        header_layout.addWidget(self.lbl_logo)
        header_layout.addSpacing(25) # Afasta um pouco mais o texto da logo

        # Layout vertical só para empilhar o Título e o Subtítulo ao lado da Logo
        titles_layout = QVBoxLayout()
        titles_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        lbl_titulo = QLabel("Bem-vindo ao Licitação 360")
        lbl_titulo.setStyleSheet("font-size: 36px; font-weight: bold; color: #FFFFFF; margin: 0px;")
        
        lbl_subtitulo = QLabel("Sistema Integrado de Automação e Inteligência em Compras Públicas")
        lbl_subtitulo.setStyleSheet("font-size: 18px; color: #A0A0A0; margin-top: 5px;")

        titles_layout.addWidget(lbl_titulo)
        titles_layout.addWidget(lbl_subtitulo)

        header_layout.addLayout(titles_layout)
        
        # Injeta o bloco do cabeçalho na tela principal
        self.main_layout.addLayout(header_layout)

        # ==========================================
        # 2. TEXTO DE APRESENTAÇÃO
        # ==========================================
        self.main_layout.addSpacing(20)

        texto_apresentacao = (
            "O Licitação 360 foi desenhado para eliminar o retrabalho e garantir a máxima eficiência "
            "nos processos de criação de atas e controle de Dispensa Eletrônica.\n\n"
            "Utilize o menu lateral para navegar entre os módulos de Criação de Atas, Dispensa Eletrônica, "
            "Indicadores de Economicidade, Configurações e Database."
        )
        lbl_desc = QLabel(texto_apresentacao)
        lbl_desc.setStyleSheet("font-size: 15px; color: #CCCCCC; line-height: 1.5;")
        lbl_desc.setWordWrap(True)
        
        self.main_layout.addWidget(lbl_desc)

        # Espaçador flexível para empurrar o Centro de Ajuda para a parte inferior da tela
        self.main_layout.addStretch()

        # ==========================================
        # 3. SESSÃO: COMO UTILIZAR O PROGRAMA
        # ==========================================
        group_ajuda = QGroupBox("Como utilizar o programa (Tutoriais)")
        group_ajuda.setStyleSheet("""
            QGroupBox {
                font-size: 16px; 
                font-weight: bold; 
                color: #8AB4F7;
                border: 1px solid #333333; 
                border-radius: 8px; 
                margin-top: 15px;
                background-color: #1A1B26;
            }
            QGroupBox::title {
                subcontrol-origin: margin; 
                left: 20px; 
                padding: 0 5px;
            }
        """)

        ajuda_layout = QHBoxLayout()
        ajuda_layout.setContentsMargins(20, 30, 20, 20)
        ajuda_layout.setSpacing(15)

        # Estilo padrão para os botões de tutorial
        btn_style = """
            QPushButton {
                background-color: #2D2E3E;
                color: white;
                border: 1px solid #444;
                border-radius: 6px;
                padding: 12px 20px;
                font-size: 14px;
                font-weight: bold;
                text-align: left;
            }
            QPushButton:hover {
                background-color: #3D3E52;
                border: 1px solid #8AB4F7;
            }
        """

        # Botão 1: Tutorial em PDF
        self.btn_pdf = QPushButton("Manual do Usuário (PDF)")
        self.btn_pdf.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_pdf.setStyleSheet(btn_style)
        self.btn_pdf.clicked.connect(lambda: self.abrir_arquivo_local("tutorial_licitacao360.pdf"))

        # Botão 2: Vídeo Tutorial
        self.btn_video = QPushButton(" Assistir Vídeo Tutorial Completo")
        self.btn_video.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_video.setStyleSheet(btn_style)
        self.btn_video.clicked.connect(self.abrir_video_tutorial)

        ajuda_layout.addWidget(self.btn_pdf)
        ajuda_layout.addWidget(self.btn_video)
        ajuda_layout.addStretch() 
        
        group_ajuda.setLayout(ajuda_layout)
        self.main_layout.addWidget(group_ajuda)

    # ==========================================
    # 4. MÉTODOS DE AÇÃO (LÓGICA DOS BOTÕES)
    # ==========================================
    
    def get_assets_path(self):
        """Descobre o caminho raiz do programa para localizar os ficheiros de ajuda."""
        if getattr(sys, 'frozen', False):
            # Quando compilado (.exe), os ficheiros encontram-se na pasta _internal gerada pelo PyInstaller
            base_dir = os.path.dirname(sys.executable)
            pasta_assets = Path(base_dir) / "_internal" / "src" / "assets" / "tutoriais"
        else:
            # Quando executado como script (.py), busca na pasta assets tradicional a partir de 'src'
            base_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
            pasta_assets = Path(base_dir) / "assets" / "tutoriais"
            
        pasta_assets.mkdir(parents=True, exist_ok=True)
        return pasta_assets

    def abrir_arquivo_local(self, nome_arquivo):
        """Abre um ficheiro local garantindo que o programa não crasha se ele não existir."""
        caminho_arquivo = self.get_assets_path() / nome_arquivo
        
        if caminho_arquivo.exists():
            try:
                if sys.platform == "win32":
                    os.startfile(caminho_arquivo)
                elif sys.platform == "darwin":  
                    subprocess.Popen(["open", str(caminho_arquivo)])
                else: 
                    subprocess.Popen(["xdg-open", str(caminho_arquivo)])
            except Exception as e:
                QMessageBox.warning(self, "Erro", f"Não foi possível abrir o ficheiro.\n{e}")
        else:
            QMessageBox.information(
                self, 
                "Ficheiro não encontrado", 
                f"O ficheiro '{nome_arquivo}' não foi encontrado.\n\nCertifique-se de que ele está na pasta:\n{self.get_assets_path()}"
            )

    def abrir_video_tutorial(self):
        """
        Abre o vídeo tutorial. 
        Pode ser um ficheiro .mp4 local OU um link do YouTube/Google Drive.
        """
        self.abrir_arquivo_local("tutorial_atas.mp4")