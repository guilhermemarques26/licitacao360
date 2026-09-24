from PyQt6.QtWidgets import *
from PyQt6.QtGui import *
from PyQt6.QtCore import *
from modules.utils.add_button import add_button, add_button_result
from modules.atas.widgets.importar_tr import TermosWidget  # Renomeado
from modules.atas.widgets.instrucoes import InstructionWidget
from modules.atas.widgets.sicaf import RegistroSICAFDialog
from modules.atas.widgets.atas import GerarAtaWidget
from pathlib import Path
from paths import PDF_DIR
from .database import DatabaseATASManager

class GerarAtasView(QMainWindow):
    instructionSignal = pyqtSignal()
    trSignal = pyqtSignal()
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

        label_ata = QLabel("Atas de Registro de Preços (Extração dos PDF)", self)
        label_ata.setStyleSheet("font-size: 26px; font-weight: bold;")
        self.main_layout.addWidget(label_ata)

        menu_widget = self.create_menu_layout()
        self.content_area = QStackedWidget()
        self.main_layout.addWidget(menu_widget)
        self.main_layout.addWidget(self.content_area)

        self.init_content_widgets()
        self.show_initial_content()

    def init_content_widgets(self):
        self.instrucoes_widget = InstructionWidget(self)
        self.content_area.addWidget(self.instrucoes_widget)

        # Widget unificado de Termos
        self.tr_widget = TermosWidget(self, self.icons)
        self.content_area.addWidget(self.tr_widget)

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
            main_window=self)
        self.content_area.addWidget(self.atas_widget)

    def show_initial_content(self):
        self.content_area.setCurrentWidget(self.instrucoes_widget)
        
    def create_menu_layout(self):
        menu_widget = QWidget()
        menu_layout = QHBoxLayout(menu_widget)
        button_layout = self.create_button_layout()
        if button_layout is not None:
            menu_layout.addLayout(button_layout)
        return menu_widget

    def create_button_layout(self):
        button_layout = QHBoxLayout()
        add_button("Instruções", "info", self.instructionSignal, button_layout, self.icons, "Exibir Instruções")
        add_button("Termos", "layers", self.trSignal, button_layout, self.icons, "Acessar Termos de Referência e Homologação")
        add_button_result("SICAF", "layers", self.sicafSignal, button_layout, self.icons, "Atualizar SICAF", lambda: self.sicaf_widget.carregar_tabelas_result() if hasattr(self, 'sicaf_widget') else None)
        add_button_result("Gerar Ata", "star", self.atasSignal, button_layout, self.icons, "Gerar nova ata", lambda: self.atas_widget.carregar_tabelas_result() if hasattr(self, 'sicaf_widget') else None)
        return button_layout

    def configurar_visualizacao_tabela_tr(self, table_view):
        if table_view.model() is None:
            return 

        # Índices corrigidos com base no SQLite (CREATE TABLE):
        # 1 = item | 2 = catalogo | 3 = descricao | 4 = descricao_detalhada
        visible_columns = [1, 2, 3, 4] 
        
        for col in range(table_view.model().columnCount()):
            if col not in visible_columns:
                table_view.hideColumn(col)
            else:
                header = table_view.model().headerData(col, Qt.Orientation.Horizontal)
                table_view.model().setHeaderData(col, Qt.Orientation.Horizontal, header)

        # Configuração de largura das colunas
        table_view.setColumnWidth(1, 50)   # item
        table_view.setColumnWidth(2, 100)  # catalogo
        table_view.setColumnWidth(3, 300)  # descricao
        
        # Faz com que a descrição detalhada (coluna 4) ocupe o restante do espaço
        table_view.horizontalHeader().setStretchLastSection(True)

    def on_pdf_dir_changed(self, new_pdf_dir):
        print(f"Novo diretório PDF definido: {new_pdf_dir}")