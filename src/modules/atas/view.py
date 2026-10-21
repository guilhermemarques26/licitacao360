from PyQt6.QtWidgets import *
from PyQt6.QtGui import *
from PyQt6.QtCore import *
from modules.atas.widgets.importar_tr import TermoReferenciaWidget
from modules.atas.widgets.instrucoes import InstructionWidget
from modules.atas.widgets.progresso_homolog import ProcessamentoWidget
from modules.atas.widgets.sicaf import RegistroSICAFDialog
from modules.atas.widgets.atas import GerarAtaWidget
from pathlib import Path
from paths import PDF_DIR
from .database import DatabaseATASManager
from modules.utils.loading import LoadingOverlay

class GerarAtasView(QMainWindow):
    instructionSignal = pyqtSignal()
    trSignal = pyqtSignal()
    homologSignal = pyqtSignal()
    sicafSignal = pyqtSignal()
    atasSignal = pyqtSignal()
    pdf_dir_changed = pyqtSignal(Path)

    def __init__(self, icons, model, database_path, parent=None):
        super().__init__(parent)
        self.icons = icons
        self.model = model
        self.database_ata_manager = DatabaseATASManager(database_path)
        self.pdf_dir = PDF_DIR
        self.setup_ui()

        self.pdf_dir_changed.connect(self.on_pdf_dir_changed)

    def setup_ui(self):
        self.main_widget = QWidget(self)
        self.setCentralWidget(self.main_widget)
        self.main_layout = QVBoxLayout(self.main_widget)
        self.loading_screen = LoadingOverlay(self.main_widget)

        # Cabeçalho da Aba
        label_ata = QLabel("Atas de Registro de Preços (Extração de PDF)", self)
        label_ata.setStyleSheet("font-size: 26px; font-weight: bold; color: #FFFFFF;")
        self.main_layout.addWidget(label_ata)

        # 1. Cria a Área de Conteúdo primeiro para que o Stepper a reconheça ao iniciar
        self.content_area = QStackedWidget()
        self.init_content_widgets()

        # 2. Injeta o Stepper Interativo (Que agora atua também como os botões de Menu)
        self.setup_stepper_menu()
        self.main_layout.addWidget(self.stepper_widget)

        # 3. Adiciona a Área de Conteúdo à tela
        self.main_layout.addWidget(self.content_area)

        self.show_initial_content()

    # =================================================================
    # STEPPER INTERATIVO E NAVEGAÇÃO (SUBSTITUI OS BOTÕES ANTIGOS)
    # =================================================================
    def setup_stepper_menu(self):
        """Monta a barra visual que atua simultaneamente como Stepper e Menu de Navegação"""
        self.stepper_widget = QWidget()
        self.stepper_layout = QHBoxLayout(self.stepper_widget)
        self.stepper_layout.setContentsMargins(0, 10, 0, 15)
        self.stepper_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Mapeamento dos Textos e das Funções de cada etapa
        self.steps_info = [
            ("Instruções", self.on_instruction_clicked),
            ("1. Termo de Referência", self.on_tr_clicked),
            ("2. Termo de Homologação", self.on_homolog_clicked),
            ("3. Consulta SICAF", self.on_sicaf_clicked),
            ("4. Gerar Ata", self.on_atas_clicked)
        ]

        self.step_buttons = []
        self.step_lines = []

        for i, (text, callback) in enumerate(self.steps_info):
            # Cria a etapa como um botão (QPushButton)
            btn = QPushButton(text)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFixedHeight(35)
            btn.clicked.connect(callback)
            
            self.stepper_layout.addWidget(btn)
            self.step_buttons.append(btn)

            # Adiciona as linhas conectando as etapas
            if i < len(self.steps_info) - 1:
                line = QFrame()
                line.setFrameShape(QFrame.Shape.HLine)
                line.setFixedSize(50, 4)
                self.stepper_layout.addWidget(line)
                self.step_lines.append(line)

        self.set_current_step(0)

    # Lógica de clique de cada etapa
    def on_instruction_clicked(self):
        self.instructionSignal.emit()
        self.set_current_step(0)

    def on_tr_clicked(self):
        self.trSignal.emit()
        self.set_current_step(1)

    def on_homolog_clicked(self):
        self.homologSignal.emit()
        self.set_current_step(2)

    def on_sicaf_clicked(self):
        self.sicafSignal.emit()
        if hasattr(self, 'sicaf_widget'):
            self.sicaf_widget.carregar_tabelas_result()
        self.set_current_step(3)

    def on_atas_clicked(self):
        self.atasSignal.emit()
        if hasattr(self, 'atas_widget'):
            self.atas_widget.carregar_tabelas_result()
        self.set_current_step(4)

    def set_current_step(self, step):
        """Atualiza a estética das etapas visuais mediante a aba ativa"""
        self.current_step = step
        
        # Estilos dos Botões no Tema Escuro
        style_active = """
            QPushButton { background-color: #8AB4F7; color: #13141F; font-weight: bold; border-radius: 17px; font-size: 13px; padding: 5px 20px; border: none; }
            QPushButton:hover { background-color: #9EC2F9; }
        """
        style_completed = """
            QPushButton { background-color: #27AE60; color: white; font-weight: bold; border-radius: 17px; font-size: 13px; padding: 5px 20px; border: none; }
            QPushButton:hover { background-color: #2ECC71; }
        """
        style_pending = """
            QPushButton { background-color: #2D2E3E; color: #A0A0A0; font-weight: bold; border-radius: 17px; font-size: 13px; padding: 5px 20px; border: none; }
            QPushButton:hover { background-color: #3D3E52; }
        """

        line_completed = "background-color: #27AE60;"
        line_pending = "background-color: #2D2E3E;"

        for i, btn in enumerate(self.step_buttons):
            if i < step:
                btn.setStyleSheet(style_completed) # Etapas concluídas (Verde)
            elif i == step:
                btn.setStyleSheet(style_active)    # Etapa atual (Azul)
            else:
                btn.setStyleSheet(style_pending)   # Etapas pendentes (Cinza)

        for i, line in enumerate(self.step_lines):
            if i < step:
                line.setStyleSheet(line_completed)
            else:
                line.setStyleSheet(line_pending)

    # =================================================================
    # WIDGETS DE CONTEÚDO
    # =================================================================
    def init_content_widgets(self):
        self.instrucoes_widget = InstructionWidget(self)
        self.content_area.addWidget(self.instrucoes_widget)

        self.tr_widget = TermoReferenciaWidget(self, self.icons)
        self.content_area.addWidget(self.tr_widget)

        self.homolog_widget = ProcessamentoWidget(
            pdf_dir=self.pdf_dir,
            icons=self.icons,
            model=self.model,
            database_ata_manager=self.database_ata_manager,
            main_window=self
        )
        self.content_area.addWidget(self.homolog_widget)

        self.sicaf_widget = RegistroSICAFDialog(
            pdf_dir=self.pdf_dir,
            model=self.model,
            icons=self.icons,
            database_ata_manager=self.database_ata_manager,
            main_window=self
        )
        self.content_area.addWidget(self.sicaf_widget)

        self.atas_widget = GerarAtaWidget(
            icons=self.icons, 
            database_ata_manager=self.database_ata_manager, 
            main_window=self
        )
        self.content_area.addWidget(self.atas_widget)

    def show_initial_content(self):
        self.content_area.setCurrentWidget(self.instrucoes_widget)
        self.set_current_step(0)

    def configurar_visualizacao_tabela_tr(self, table_view):
        if table_view.model() is None:
            print("O modelo de dados não foi configurado para table_view.")
            return  

        visible_columns = [1, 2, 3, 4]
        for col in range(table_view.model().columnCount()):
            if col not in visible_columns:
                table_view.hideColumn(col)
            else:
                header = table_view.model().headerData(col, Qt.Orientation.Horizontal)
                table_view.model().setHeaderData(col, Qt.Orientation.Horizontal, header)

        table_view.setColumnWidth(1, 40)
        table_view.setColumnWidth(2, 70)
        table_view.setColumnWidth(3, 200)
        table_view.horizontalHeader().setStretchLastSection(True)

    def on_pdf_dir_changed(self, new_pdf_dir):
        print(f"Novo diretório PDF definido: {new_pdf_dir}")