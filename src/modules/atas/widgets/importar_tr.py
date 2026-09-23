import os
import pandas as pd
import pdfplumber
from PyQt6.QtWidgets import *
from PyQt6.QtGui import *
from PyQt6.QtCore import *
from modules.utils.add_button import add_button

class PreencherTabelaDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Seleção de Documentos")
        self.resize(500, 250)
        self.caminho_tr = None
        self.caminho_homolog = None

        layout = QVBoxLayout(self)
        layout.setSpacing(15)

        # --- SEÇÃO TR ---
        self.lbl_instrucao_tr = QLabel("1. Selecione o arquivo PDF do Termo de Referência:")
        self.lbl_instrucao_tr.setFont(QFont('Arial', 10, QFont.Weight.Bold))
        layout.addWidget(self.lbl_instrucao_tr)

        self.btn_tr = QPushButton("Selecionar Termo de Referência")
        self.btn_tr.clicked.connect(self.selecionar_pdf_tr)
        layout.addWidget(self.btn_tr)

        self.lbl_arquivo_tr = QLabel("Nenhum TR selecionado.")
        self.lbl_arquivo_tr.setStyleSheet("color: gray; font-style: italic;")
        self.lbl_arquivo_tr.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.lbl_arquivo_tr)

        # --- SEÇÃO HOMOLOGAÇÃO ---
        self.lbl_instrucao_homolog = QLabel("2. Selecione a PASTA com os Termos de Homologação:")
        self.lbl_instrucao_homolog.setFont(QFont('Arial', 10, QFont.Weight.Bold))
        layout.addWidget(self.lbl_instrucao_homolog)

        self.btn_homolog = QPushButton("Selecionar Pasta de Homologação")
        self.btn_homolog.clicked.connect(self.selecionar_pasta_homolog)
        layout.addWidget(self.btn_homolog)

        self.lbl_arquivo_homolog = QLabel("Nenhuma pasta selecionada.")
        self.lbl_arquivo_homolog.setStyleSheet("color: gray; font-style: italic;")
        self.lbl_arquivo_homolog.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.lbl_arquivo_homolog)

        # --- AÇÕES ---
        botoes_layout = QHBoxLayout()
        self.btn_cancelar = QPushButton("Cancelar")
        self.btn_cancelar.clicked.connect(self.reject)
        
        self.btn_preencher = QPushButton("Processar Documentos")
        self.btn_preencher.setEnabled(False) 
        self.btn_preencher.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold;")
        self.btn_preencher.clicked.connect(self.accept)

        botoes_layout.addWidget(self.btn_cancelar)
        botoes_layout.addWidget(self.btn_preencher)
        layout.addLayout(botoes_layout)

    def selecionar_pdf_tr(self):
        caminho, _ = QFileDialog.getOpenFileName(self, "Selecione o Termo de Referência", "", "Arquivos PDF (*.pdf)")
        if caminho:
            self.caminho_tr = caminho
            self.lbl_arquivo_tr.setText(f"TR: {caminho.split('/')[-1]}")
            self.lbl_arquivo_tr.setStyleSheet("color: black; font-weight: bold;")
            self.verificar_preenchimento()

    def selecionar_pasta_homolog(self):
        caminho = QFileDialog.getExistingDirectory(self, "Selecione a Pasta de Homologação")
        if caminho:
            self.caminho_homolog = caminho
            self.lbl_arquivo_homolog.setText(f"Pasta: {caminho.split('/')[-1]}")
            self.lbl_arquivo_homolog.setStyleSheet("color: black; font-weight: bold;")
            self.verificar_preenchimento()

    def verificar_preenchimento(self):
        if self.caminho_tr and self.caminho_homolog:
            self.btn_preencher.setEnabled(True)


class TermosWidget(QWidget): 
    preencherTabelaSignal = pyqtSignal() 
    iniciarExtracaoDuplaSignal = pyqtSignal(str, str)
    limparTabelaSignal = pyqtSignal() 
    configurarSqlModelSignal = pyqtSignal() 

    def __init__(self, parent, icons):
        super().__init__(parent)
        self.setWindowTitle("Especificação dos Termos")
        self.resize(800, 600)
        self.parent = parent
        self.icons = icons
        
        self.layout = QVBoxLayout(self)
        
        title_layout = QHBoxLayout()
        title_layout.addStretch()
        
        title = QLabel("Extração e Cruzamento de Termos")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setFont(QFont('Arial', 16, QFont.Weight.Bold))
        title_layout.addWidget(title)

        
        add_button("Preencher Tabela", "excel_down", self.preencherTabelaSignal, title_layout, self.icons, tooltip="Cruza dados do TR e Homologação", button_size=(200, 30))
        self.preencherTabelaSignal.connect(self.abrir_modal_preencher)
        
        add_button("Limpar Tabela", "delete", self.limparTabelaSignal, title_layout, self.icons, tooltip="Limpa todos os dados da tabela", button_size=(200, 30))

        title_layout.addStretch()
        self.layout.addLayout(title_layout)
        
        title1 = QLabel("Nesta aba o sistema cruza as especificações do Termo de Referência com os vencedores do Termo de Homologação.")
        title1.setAlignment(Qt.AlignmentFlag.AlignLeft)
        title1.setFont(QFont('Arial', 12))
        self.layout.addWidget(title1)

        self.table_view = QTableView(self)
        self.table_view.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.table_view.verticalHeader().setVisible(False) 
        self.layout.addWidget(self.table_view)

        self.table_view.setStyleSheet("""
            QTableView { background-color: #F3F3F3; color: #333333; gridline-color: #CCCCCC; font-size: 14px;}
            QTableView::item:selected { background-color: #E0E0E0; color: #000000; }
            QTableView::item { padding: 5px; }
            QHeaderView::section { background-color: #D6D6D6; font-weight: bold; font-size: 14px; padding: 4px; border: 1px solid #CCCCCC; }
        """)

        self.configurarSqlModelSignal.emit()

    def abrir_modal_preencher(self):
        dialog = PreencherTabelaDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            if dialog.caminho_tr and dialog.caminho_homolog:
                # Dispara o sinal para o Controller orquestrar o processo
                self.iniciarExtracaoDuplaSignal.emit(dialog.caminho_tr, dialog.caminho_homolog)

    def extrair_dados_tr(self, pdf_path):
        """Retorna APENAS o Item, Catálogo e Especificação do TR."""
        try:
            linhas_brutas = []
            config_tabela = {"vertical_strategy": "lines", "horizontal_strategy": "text", "intersection_y_tolerance": 15}

            with pdfplumber.open(pdf_path) as pdf:
                for page in pdf.pages:
                    tables = page.extract_tables(table_settings=config_tabela)
                    if not tables:
                        tables = page.extract_tables()
                    for table in tables:
                        for row in table:
                            if row: linhas_brutas.append(row)

            dados = []
            current_item = ["", "", ""] # [0] item, [1] especificacao, [2] catalogo

            def salvar_item_atual():
                if current_item[0] or current_item[1]:
                    dados.append({
                        'item': current_item[0],
                        'descricao_detalhada': current_item[1],
                        'catalogo': current_item[2]
                    })

            for row in linhas_brutas:
                row = [str(cell).replace('\n', ' ').strip() if cell else "" for cell in row]
                while len(row) < 4: row.append("")
                
                texto_linha = "".join(row).strip().lower()
                termos_ignorar = ["manual de modelos", "modelos de licitações", "licitações e contratos", "consultoria-geral", "da união", "secretaria de gestão", "gestão e inovação", "e inovação", "atualização:", "maio/2023", "câmara nacional"]
                
                if any(termo in texto_linha for termo in termos_ignorar) or not texto_linha or 'ITEM' in row[0].upper() or 'DESCRIÇÃO' in row[1].upper():
                    continue

                # Ignoramos row[1] (Descrição do TR), capturando apenas Item, Especificação e Catmat
                r_item, r_spec, r_cat = row[0], row[2], row[3] 
                
                is_new = False
                if r_item.isdigit():
                    if current_item[0] != "": is_new = True
                else:
                    if r_cat != "" and current_item[2] != "": is_new = True
                        
                if is_new:
                    salvar_item_atual()
                    current_item = ["", "", ""]
                
                if r_item.isdigit(): current_item[0] = r_item
                if r_item and not r_item.isdigit(): current_item[1] = (current_item[1] + " " + r_item).strip()
                if r_spec: current_item[1] = (current_item[1] + " " + r_spec).strip()
                if r_cat: current_item[2] = (current_item[2] + " " + r_cat).strip()

            salvar_item_atual()

            if dados:
                df = pd.DataFrame(dados)
                for col in ['descricao_detalhada', 'catalogo']:
                    df[col] = df[col].apply(lambda x: " ".join(str(x).split()) if x else "")
                # Retorna estritamente as 3 colunas de interesse
                return df[['item', 'catalogo', 'descricao_detalhada']]
            
            return pd.DataFrame()
            
        except Exception as e:
            print(f"Erro no TR: {e}")
            return pd.DataFrame()