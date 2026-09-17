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
        self.setWindowTitle("Termo de Referência")
        self.resize(450, 150)
        self.caminho_pdf = None

        layout = QVBoxLayout(self)

        self.label_instrucao = QLabel("Selecione o arquivo PDF do Termo de Referência:")
        self.label_instrucao.setFont(QFont('Arial', 10, QFont.Weight.Bold))
        layout.addWidget(self.label_instrucao)

        self.btn_selecionar = QPushButton("Selecionar Termo de Referência")
        self.btn_selecionar.clicked.connect(self.selecionar_pdf)
        layout.addWidget(self.btn_selecionar)

        self.label_arquivo = QLabel("Nenhum arquivo selecionado.")
        self.label_arquivo.setStyleSheet("color: gray; font-style: italic;")
        self.label_arquivo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.label_arquivo)

        botoes_layout = QHBoxLayout()
        
        self.btn_cancelar = QPushButton("Cancelar")
        self.btn_cancelar.clicked.connect(self.reject)
        
        self.btn_preencher = QPushButton("Preencher")
        self.btn_preencher.setEnabled(False) 
        self.btn_preencher.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold;")
        self.btn_preencher.clicked.connect(self.accept)

        botoes_layout.addWidget(self.btn_cancelar)
        botoes_layout.addWidget(self.btn_preencher)
        layout.addLayout(botoes_layout)

    def selecionar_pdf(self):
        caminho, _ = QFileDialog.getOpenFileName(
            self, 
            "Selecione o Termo de Referência", 
            "", 
            "Arquivos PDF (*.pdf)"
        )
        if caminho:
            self.caminho_pdf = caminho
            nome_arquivo = caminho.split("/")[-1]
            self.label_arquivo.setText(f"Arquivo: {nome_arquivo}")
            self.label_arquivo.setStyleSheet("color: black; font-weight: bold;")
            self.btn_preencher.setEnabled(True)


class TermoReferenciaWidget(QWidget): 
    # Sinais atualizados
    preencherTabelaSignal = pyqtSignal()
    limparTabelaSignal = pyqtSignal() # <-- NOVO SINAL ADICIONADO
    dadosExtraidosSignal = pyqtSignal(object) 
    carregarTabela = pyqtSignal()  
    configurarSqlModelSignal = pyqtSignal() 

    def __init__(self, parent, icons):
        super().__init__(parent)
        self.setWindowTitle("Termo de Referência")
        self.resize(800, 600)
        self.parent = parent
        self.icons = icons
        
        # Configuração do layout principal
        self.layout = QVBoxLayout(self)
        
        # Configuração do título e botões
        title_layout = QHBoxLayout()
        title_layout.addStretch()
        
        title = QLabel("Especificação do Termo de Referência")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setFont(QFont('Arial', 16, QFont.Weight.Bold))
        title_layout.addWidget(title)

        # Botão de preencher tabela
        add_button("Preencher Tabela", "excel_down", self.preencherTabelaSignal, title_layout, self.icons, tooltip="Extrai os dados do TR em PDF e preenche a tabela", button_size=(200, 30))
        self.preencherTabelaSignal.connect(self.abrir_modal_preencher)
        
        # NOVO: Botão de limpar tabela
        add_button("Limpar Tabela", "delete", self.limparTabelaSignal, title_layout, self.icons, tooltip="Limpa todos os dados da tabela atual", button_size=(200, 30))

        title_layout.addStretch()
        self.layout.addLayout(title_layout)
        
        title1 = QLabel("Este passo é necessário para obter as especificações do termo de referência, que não constam no termo de homologação ou no comprasnet.")
        title1.setAlignment(Qt.AlignmentFlag.AlignLeft)
        title1.setFont(QFont('Arial', 12))
        self.layout.addWidget(title1)

        title2 = QLabel("Importante! O índice da tabela deve ser 'item', 'catalogo', 'descricao' e 'descricao_detalhada'.")
        title2.setAlignment(Qt.AlignmentFlag.AlignLeft)
        title2.setFont(QFont('Arial', 12))
        self.layout.addWidget(title2)

        # Configurar o QTableView para exibir os dados
        self.table_view = QTableView(self)
        self.table_view.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.table_view.verticalHeader().setVisible(False) 
        self.layout.addWidget(self.table_view)

        # Aplicar estilo CSS
        self.table_view.setStyleSheet("""
            QTableView {
                background-color: #F3F3F3;
                color: #333333;
                gridline-color: #CCCCCC;
                alternate-background-color: #FFFFFF;
                selection-background-color: #E0E0E0;
                selection-color: #000000;
                border: 1px solid #CCCCCC;
                font-size: 14px;
            }
            QTableView::item:selected {
                background-color: #E0E0E0;
                color: #000000;
            }
            QTableView::item {
                border: 1px solid transparent;
                padding: 5px;
            }
            QHeaderView::section {
                background-color: #D6D6D6;
                color: #333333;
                font-weight: bold;
                font-size: 14px;
                padding: 4px;
                border: 1px solid #CCCCCC;
            }
        """)

        self.configurarSqlModelSignal.emit()

    def abrir_modal_preencher(self):
        dialog = PreencherTabelaDialog(self)
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            pdf_path = dialog.caminho_pdf
            if pdf_path:
                QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
                sucesso = self.extrair_dados_tr(pdf_path)
                QApplication.restoreOverrideCursor()

                if sucesso:
                    QMessageBox.information(self, "Sucesso", "Tabela preenchida com sucesso a partir do Termo de Referência!")
                else:
                    QMessageBox.warning(self, "Erro", "Não foi possível encontrar itens no PDF. Verifique se o formato da tabela é o padrão.")

    def extrair_dados_tr(self, pdf_path):
        try:
            linhas_brutas = []
            
            config_tabela = {
                "vertical_strategy": "lines",
                "horizontal_strategy": "text",
                "intersection_y_tolerance": 15
            }

            # 1. Extrai todas as linhas
            with pdfplumber.open(pdf_path) as pdf:
                for page in pdf.pages:
                    tables = page.extract_tables(table_settings=config_tabela)
                    if not tables:
                        tables = page.extract_tables()
                        
                    for table in tables:
                        for row in table:
                            if row:
                                linhas_brutas.append(row)

            # 2. PROCESSAMENTO INTELIGENTE
            dados = []
            current_item = ["", "", "", ""] 

            def salvar_item_atual():
                if current_item[0] or current_item[1]:
                    dados.append({
                        'item': current_item[0],
                        'catalogo': current_item[3],
                        'descricao': current_item[1],
                        'descricao_detalhada': current_item[2]
                    })

            for row in linhas_brutas:
                row = [str(cell).replace('\n', ' ').strip() if cell else "" for cell in row]
                while len(row) < 4:
                    row.append("")
                
                texto_linha = "".join(row).strip()
                texto_linha_lower = texto_linha.lower()
                
                # --- NOVO: FILTRO ANTI-RODAPÉ E CABEÇALHOS DA AGU ---
                termos_ignorar = [
                    "manual de modelos",
                    "consultoria-geral",
                    "secretaria de gestão",
                    "atualização:",
                    "câmara nacional de modelos"
                ]
                
                # Se a linha contiver algum dos termos do rodapé, pula para a próxima
                if any(termo in texto_linha_lower for termo in termos_ignorar):
                    continue

                # Ignora linhas vazias ou cabeçalhos da tabela repetidos
                if not texto_linha or 'ITEM' in row[0].upper() or 'DESCRIÇÃO' in row[1].upper():
                    continue

                r_item = row[0]
                r_desc = row[1]
                r_spec = row[2]
                r_cat = row[3]
                
                is_new = False
                
                # REGRA 1
                if r_item.isdigit():
                    if current_item[0] != "":
                        is_new = True
                
                # REGRA 2
                else:
                    if r_cat != "" and current_item[3] != "":
                        is_new = True
                        
                if is_new:
                    salvar_item_atual()
                    current_item = ["", "", "", ""]
                
                # MESCLAGEM
                if r_item.isdigit():
                    current_item[0] = r_item
                
                if r_item and not r_item.isdigit():
                    current_item[2] = (current_item[2] + " " + r_item).strip()
                    
                if r_desc:
                    current_item[1] = (current_item[1] + " " + r_desc).strip()
                if r_spec:
                    current_item[2] = (current_item[2] + " " + r_spec).strip()
                if r_cat:
                    current_item[3] = (current_item[3] + " " + r_cat).strip()

            salvar_item_atual()

            # 3. CONVERSÃO E LIMPEZA
            if dados:
                df = pd.DataFrame(dados)
                
                for col in ['descricao', 'descricao_detalhada', 'catalogo']:
                    df[col] = df[col].apply(lambda x: " ".join(str(x).split()) if x else "")

                df = df[['item', 'catalogo', 'descricao', 'descricao_detalhada']]
                
                self.dadosExtraidosSignal.emit(df)
                return True
            
            return False
            
        except Exception as e:
            import traceback
            print(f"Erro durante a extração do PDF: {e}")
            traceback.print_exc()
            return False  # Posições: [0] item, [1] descricao, [2] especificacao, [3] catmat

            def salvar_item_atual():
                # Só salva se tiver um número de item ou descrição válida
                if current_item[0] or current_item[1]:
                    dados.append({
                        'item': current_item[0],
                        'catalogo': current_item[3],
                        'descricao': current_item[1],
                        'descricao_detalhada': current_item[2]
                    })

            for row in linhas_brutas:
                # Limpa a linha e garante que tenha pelo menos 4 colunas
                row = [str(cell).replace('\n', ' ').strip() if cell else "" for cell in row]
                while len(row) < 4:
                    row.append("")
                
                r_item = row[0]
                r_desc = row[1]
                r_spec = row[2]
                r_cat = row[3]
                
                texto_linha = "".join(row).strip()
                if not texto_linha or 'ITEM' in r_item.upper() or 'DESCRIÇÃO' in r_desc.upper():
                    continue

                is_new = False
                
                # REGRA 1: A linha atual tem um número de item, e o nosso 'current_item' já tem um número.
                # Conclusão: Estamos iniciando um item totalmente novo.
                if r_item.isdigit():
                    if current_item[0] != "":
                        is_new = True
                
                # REGRA 2 (O SEU CASO DA IMAGEM): A linha atual NÃO tem número de item,
                # mas ELA TEM um CATMAT e o nosso 'current_item' TAMBÉM JÁ TEM um CATMAT.
                # Conclusão: É impossível um item ter dois CATMATs. Portanto, essa linha 
                # é o início de um novo item, cujo número só vai aparecer na próxima página!
                else:
                    if r_cat != "" and current_item[3] != "":
                        is_new = True
                        
                # Se detectou que é um item novo, salva o que estava na memória e limpa
                if is_new:
                    salvar_item_atual()
                    current_item = ["", "", "", ""]
                
                # MESCLA os dados da linha lida com o item que está na memória
                if r_item.isdigit():
                    current_item[0] = r_item
                
                # Prevenção de falha do pdfplumber: se o texto da col 0 não for número, joga para especificação
                if r_item and not r_item.isdigit():
                    current_item[2] = (current_item[2] + " " + r_item).strip()
                    
                if r_desc:
                    current_item[1] = (current_item[1] + " " + r_desc).strip()
                if r_spec:
                    current_item[2] = (current_item[2] + " " + r_spec).strip()
                if r_cat:
                    current_item[3] = (current_item[3] + " " + r_cat).strip()

            # Ao final do loop, salva o último item que ficou na memória
            salvar_item_atual()

            # 3. CONVERSÃO E LIMPEZA
            if dados:
                df = pd.DataFrame(dados)
                
                # Limpeza final: remove espaços duplos criados pela junção de páginas
                for col in ['descricao', 'descricao_detalhada', 'catalogo']:
                    df[col] = df[col].apply(lambda x: " ".join(str(x).split()) if x else "")

                df = df[['item', 'catalogo', 'descricao', 'descricao_detalhada']]
                
                self.dadosExtraidosSignal.emit(df)
                return True
            
            return False
            
        except Exception as e:
            import traceback
            print(f"Erro durante a extração do PDF: {e}")
            traceback.print_exc() # Isso mostrará a linha exata do erro no seu terminal
            return False