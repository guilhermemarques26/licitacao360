import os
import pandas as pd
import fitz
import re
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
        import pdfplumber
        import pandas as pd
        import re

        try:
            linhas_brutas = []
            
            with pdfplumber.open(pdf_path) as pdf:
                for page in pdf.pages:
                    tables = page.extract_tables()
                    if not tables: continue
                    for table in tables:
                        for row in table:
                            if not any(row): continue
                            
                            # DESDOBRADOR DE CÉLULAS (Mantido, pois resolve os itens fundidos perfeitamente)
                            max_lines = 1
                            for cell in row:
                                if cell:
                                    linhas_celula = str(cell).split('\n')
                                    if len(linhas_celula) > max_lines:
                                        max_lines = len(linhas_celula)
                                        
                            for i in range(max_lines):
                                new_row = []
                                for cell in row:
                                    if not cell:
                                        new_row.append("")
                                    else:
                                        linhas_celula = str(cell).split('\n')
                                        if i < len(linhas_celula):
                                            new_row.append(linhas_celula[i].strip())
                                        else:
                                            new_row.append("")
                                if any(new_row):
                                    linhas_brutas.append(new_row)

            dados = {}
            current_item = None
            orphan_cat = ""
            orphan_spec = ""

            for row in linhas_brutas:
                row_clean = [str(c).replace('\n', ' ').strip() for c in row]
                texto_linha = " ".join(row_clean).lower()
                
                # Ignora rodapés e cabeçalhos
                termos_ignorar = ["manual de modelos", "consultoria-geral", "da união", "secretaria de gestão", "atualização:", "câmara nacional"]
                if any(termo in texto_linha for termo in termos_ignorar):
                    continue
                if 'item' in str(row_clean[0]).lower() or ('descrição' in texto_linha and 'especificação' in texto_linha):
                    continue

                r_item = ""
                r_cat = ""
                spec_parts = []

                # 1. IDENTIFICA O ITEM (Sempre na primeira célula)
                primeira_celula = re.sub(r'[^\d]', '', row_clean[0])
                if primeira_celula and row_clean[0].strip() == primeira_celula:
                    r_item = primeira_celula

                # 2. O ARRASTÃO: Varre todas as células da linha (da esq. para a dir.)
                for i, cell in enumerate(row_clean):
                    if i == 0 and r_item: 
                        continue # Pula a célula do Item para não a juntar ao texto
                        
                    if not cell: 
                        continue

                    # Identifica o Catmat (limpa aspas residuais)
                    limpo_cat = re.sub(r'[^\d]', '', cell)
                    if not r_cat and len(limpo_cat) >= 5 and len(limpo_cat) <= 7 and re.fullmatch(r'\d{5,7}', limpo_cat):
                        if len(cell) <= 12: # Garante que é uma célula curta com o código
                            r_cat = limpo_cat
                            continue
                    
                    # Filtro anti-lixo numérico: Ignora Quantidades e Valores Financeiros (Ex: "566", "14,00", "7.924,00")
                    if re.fullmatch(r'\d{1,4}', cell) or re.fullmatch(r'\d{1,3}(?:\.\d{3})*(?:,\d{2})', cell):
                        continue
                        
                    # Se não é o Item, não é o Catmat, e não é um número solto... é a ESPECIFICAÇÃO!
                    spec_parts.append(cell)

                r_spec = " ".join(spec_parts).strip()

                # 3. LÓGICA DE ALOCAÇÃO (A mesma que salvou os Catmats!)
                if r_item:
                    current_item = str(int(r_item))
                    if current_item not in dados:
                        dados[current_item] = {"catalogo": "", "descricao_detalhada": ""}
                    
                    if orphan_cat:
                        dados[current_item]["catalogo"] = orphan_cat
                        orphan_cat = ""
                    if orphan_spec:
                        dados[current_item]["descricao_detalhada"] += (" " + orphan_spec)
                        orphan_spec = ""
                        
                    if r_cat: dados[current_item]["catalogo"] = r_cat
                    if r_spec: dados[current_item]["descricao_detalhada"] += (" " + r_spec)
                
                else: 
                    if current_item:
                        if r_cat and dados[current_item]["catalogo"] and dados[current_item]["catalogo"] != r_cat:
                            orphan_cat = r_cat
                            if r_spec: orphan_spec += (" " + r_spec)
                        else:
                            if orphan_cat or orphan_spec:
                                if r_cat: orphan_cat = r_cat
                                if r_spec: orphan_spec += (" " + r_spec)
                            else:
                                if r_cat: dados[current_item]["catalogo"] = r_cat
                                if r_spec: dados[current_item]["descricao_detalhada"] += (" " + r_spec)
                    else:
                        if r_cat: orphan_cat = r_cat
                        if r_spec: orphan_spec += (" " + r_spec)

            lista_dados = []
            for k, v in dados.items():
                # Remove espaços duplos e prepara a injeção
                desc = " ".join(v["descricao_detalhada"].split())
                lista_dados.append({
                    "item": k,
                    "catalogo": v["catalogo"],
                    "descricao_detalhada": desc
                })

            if lista_dados:
                df = pd.DataFrame(lista_dados)
                for col in ['item', 'catalogo', 'descricao_detalhada']:
                    if col not in df.columns: 
                        df[col] = ""
                return df[['item', 'catalogo', 'descricao_detalhada']]
            
            return pd.DataFrame()
            
        except Exception as e:
            print(f"Erro no TR: {e}")
            import traceback
            traceback.print_exc()
            return pd.DataFrame()