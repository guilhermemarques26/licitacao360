from PyQt6.QtWidgets import *
from PyQt6.QtGui import *
from PyQt6.QtCore import *
import re
import time
import os
import pandas as pd
import pdfplumber

class Worker(QThread):
    processing_complete = pyqtSignal(list)  
    update_context_signal = pyqtSignal(str) 
    progress_signal = pyqtSignal(int)  

    tabela_base_pronta = pyqtSignal(pd.DataFrame) 

    def __init__(self, pdf_dir, modo="completo", parent=None):
        super().__init__(parent)
        self.pdf_dir = pdf_dir
        self.modo = modo
        self.pdf_path_str = str(pdf_dir)

    def run(self):
        try:
            if self.modo == 'tabela_base':
                self._processar_para_tabela_base()
            
            elif self.modo == 'completo':
                extracted_data = []
                pdf_files = list(self.pdf_dir.glob("*.pdf"))
                total_files = len(pdf_files)

                for index, pdf_file in enumerate(pdf_files):
                    text = self.process_single_pdf(pdf_file)
                    if text:
                        extracted_data.append({
                            "nome_arquivo": pdf_file.name,
                            "text": text
                        })
                        self.update_context_signal.emit(f"Análise do PDF {pdf_file.name} concluída com êxito.")
                    else:
                        self.update_context_signal.emit(f"Não foi possível obter os dados corretamente de {pdf_file.name}.")

                    progress = int((index + 1) / total_files * 100)
                    self.progress_signal.emit(progress)
                    QThread.msleep(100)
                
                self.processing_complete.emit(extracted_data)

        except Exception as e:
            self.update_context_signal.emit(f"ERRO CRÍTICO no Worker: {e}")
            
    def _processar_para_tabela_base(self):
        pdf_files = [f for f in os.listdir(self.pdf_path_str) if f.lower().endswith('.pdf')]
        
        path_tr = None
        for arquivo in pdf_files:
            if "termo" in arquivo.lower() and "referencia" in arquivo.lower():
                path_tr = os.path.join(self.pdf_path_str, arquivo)
                self.update_context_signal.emit(f"Termo de Referência encontrado: {arquivo}")
                break
        
        if not path_tr:
            self.update_context_signal.emit("ERRO: PDF do Termo de Referência não encontrado na pasta.")
            return

        df_tr = pd.DataFrame()
        try:
            self.update_context_signal.emit("Extraindo tabela de itens do TR...")
            with pdfplumber.open(path_tr) as pdf:
                todas_as_tabelas = []
                for i, page in enumerate(pdf.pages):
                    self.progress_signal.emit(int((i + 1) / len(pdf.pages) * 50)) 
                    tabelas_pagina = page.extract_tables()
                    if tabelas_pagina:
                        todas_as_tabelas.extend(tabelas_pagina[0])
            
            if todas_as_tabelas:
                colunas_desejadas = ['item', 'catalogo', 'descricao_detalhada']
                df_tr = pd.DataFrame(todas_as_tabelas[1:], columns=todas_as_tabelas[0])
                df_tr = df_tr.iloc[:, :3] 
                df_tr.columns = colunas_desejadas
                self.update_context_signal.emit(f"Sucesso: {len(df_tr)} itens extraídos do TR.")
            else:
                self.update_context_signal.emit("AVISO: Nenhuma tabela encontrada no arquivo TR.")

        except Exception as e:
            self.update_context_signal.emit(f"Falha ao extrair dados do TR: {e}")
            return

        dados_homologacao = []
        regex_item = re.compile(r"Item:\s*(\d+)")
        regex_desc = re.compile(r"Descrição:\s*([^\n]+)")

        arquivos_homologacao = [f for f in pdf_files if "homologacao" in f.lower()]
        total_homologacao = len(arquivos_homologacao)

        for index, arquivo in enumerate(arquivos_homologacao):
            self.progress_signal.emit(50 + int((index + 1) / total_homologacao * 50)) 
            path_arquivo = os.path.join(self.pdf_path_str, arquivo)
            try:
                with pdfplumber.open(path_arquivo) as pdf:
                    texto_completo = "".join([page.extract_text() for page in pdf.pages if page.extract_text()])
                    
                    itens_matches = list(regex_item.finditer(texto_completo))
                    desc_matches = list(regex_desc.finditer(texto_completo))

                    for n_match, d_match in zip(itens_matches, desc_matches):
                        dados_homologacao.append({
                            'item': n_match.group(1).strip(),
                            'descricao': d_match.group(1).strip()
                        })
            except Exception as e:
                self.update_context_signal.emit(f"AVISO: Não foi possível ler {arquivo}: {e}")
        
        df_homolog = pd.DataFrame(dados_homologacao)
        self.update_context_signal.emit(f"{len(df_homolog)} descrições curtas extraídas dos relatórios.")

        if not df_tr.empty:
            if not df_homolog.empty:
                df_tr['item'] = df_tr['item'].astype(str)
                df_homolog['item'] = df_homolog['item'].astype(str)
                df_final = pd.merge(df_tr, df_homolog, on='item', how='left')
                self.update_context_signal.emit("Dados do TR e da Homologação combinados.")
            else:
                df_final = df_tr
                df_final['descricao'] = '' 
                self.update_context_signal.emit("AVISO: Nenhum dado de homologação para combinar.")
            
            self.tabela_base_pronta.emit(df_final)
        else:
            self.update_context_signal.emit("ERRO: Não foi possível gerar a tabela base pois o TR está vazio.")
        
        self.progress_signal.emit(100)

    def _processar_modo_completo(self):
        extracted_data = []
        pdf_files = list(self.pdf_dir.glob("*.pdf"))
        total_files = len(pdf_files)

        for index, pdf_file in enumerate(pdf_files):
            text = self.process_single_pdf(pdf_file) 
            if text:
                extracted_data.append({
                    "nome_arquivo": pdf_file.name,
                    "text": text
                })
                self.update_context_signal.emit(f"Análise do PDF {pdf_file.name} concluída com êxito.")
            else:
                self.update_context_signal.emit(f"Não foi possível obter os dados corretamente de {pdf_file.name}.")

            progress = int((index + 1) / total_files * 100)
            self.progress_signal.emit(progress)
            QThread.msleep(100)

        self.processing_complete.emit(extracted_data)


    def process_single_pdf(self, pdf_file):
        try:
            with pdfplumber.open(pdf_file) as pdf:
                text = ""
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
                    else:
                        self.update_context_signal.emit(f"Aviso: Página de {pdf_file.name} não contém texto extraível.")
                return text
        except Exception as e:
            self.update_context_signal.emit(f"Erro ao processar {pdf_file.name}: {e}")
            return None


class CustomTreeView(QTreeView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.cnpj = ""

    def contextMenuEvent(self, event):
        index = self.indexAt(event.pos())
        if not index.isValid():
            return

        item = self.model().itemFromIndex(index)
        if item and " - " in item.text():
            doc = QTextDocument()
            doc.setHtml(item.text())
            plain_text = doc.toPlainText()

            if " - " in plain_text:
                self.cnpj = plain_text.split(' - ')[0]

            menu = QMenu(self)
            copyAction = QAction(f"Copiar CNPJ {self.cnpj}", self)
            copyAction.triggered.connect(lambda: self.copy_cnpj(plain_text))
            menu.addAction(copyAction)
            menu.exec(event.globalPos())

    def copy_cnpj(self, text):
        if " - " in text:
            self.cnpj = text.split(' - ')[0]  
        QApplication.clipboard().setText(self.cnpj)
        QToolTip.showText(QCursor.pos(), f"CNPJ {self.cnpj} copiado para área de transferência", self)

    def mousePressEvent(self, event):
        index = self.indexAt(event.pos())
        if index.isValid() and event.button() == Qt.MouseButton.LeftButton:
            self.setExpanded(index, not self.isExpanded(index))
            
            if self.isExpanded(index):
                model = self.model()
                numRows = model.rowCount(index)
                for row in range(numRows):
                    childIndex = model.index(row, 0, index)
                    self.setExpanded(childIndex, True)
                    self.collapseAllChildren(childIndex)

        super().mousePressEvent(event)

    def collapseAllChildren(self, parentIndex):
        model = self.model()
        numRows = model.rowCount(parentIndex)
        for row in range(numRows):
            childIndex = model.index(row, 0, parentIndex)
            self.collapseAllChildren(childIndex)
            self.setExpanded(childIndex, False)

    def setup_treeview(self):
        if not hasattr(self, 'treeView') or self.treeView is None:
            self.treeView = CustomTreeView()  

        if hasattr(self, 'message_label') and self.message_label:
            self.message_label.hide()

        if not hasattr(self, 'model') or self.model is None:
            self.model = QStandardItemModel()  

        self.treeView.setModel(self.model)

        if hasattr(self, 'dynamic_content_layout') and self.dynamic_content_layout is not None:
            while self.dynamic_content_layout.count():
                widget_to_remove = self.dynamic_content_layout.takeAt(0).widget()
                if widget_to_remove is not None:
                    widget_to_remove.deleteLater()

            self.dynamic_content_layout.addWidget(self.treeView)

        self.treeView.header().setDefaultAlignment(Qt.AlignmentFlag.AlignCenter)
        self.treeView.setAnimated(True)  
        self.treeView.setUniformRowHeights(True)  
        self.treeView.setItemsExpandable(True)  
        self.treeView.setExpandsOnDoubleClick(False)  
        self.setup_treeview_styles()

    def setup_treeview_styles(self):
        header = self.treeView.header()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        
class CustomProgressBar(QProgressBar):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFont(QFont("Arial", 16))  
        self.setTextVisible(False)  

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setPen(QColor(Qt.GlobalColor.black))
        rect = self.rect()
        font_metrics = self.fontMetrics()
        progress_percent = self.value()
        text = f"{progress_percent}%" if progress_percent >= 0 else ""
        text_width = font_metrics.horizontalAdvance(text)
        text_height = font_metrics.height()
        painter.drawText(int((rect.width() - text_width) / 2), int((rect.height() + text_height) / 2), text)
        painter.end()


class TreeViewWindow(QDialog): 
    def __init__(self, dataframe, icons_dir, database_ata_manager, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Resultados do Processamento")
        self.icons_dir = icons_dir
        self.database_ata_manager = database_ata_manager  
        self.setMinimumSize(800, 600)

        # =================================================================
        # BLINDAGEM VISUAL: Corta o "R$" ignorando as quebras de linha (re.DOTALL)
        # Isso limpa a tabela caso a base de dados ainda tenha resquícios antigos
        # =================================================================
        if 'unidade' in dataframe.columns:
            dataframe['unidade'] = dataframe['unidade'].astype(str).apply(
                lambda x: re.sub(r'\s*R\$.*', '', x, flags=re.DOTALL | re.IGNORECASE).strip()
            )
            
        self.dataframe = dataframe
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        self.treeView = CustomTreeView()
        self.populate_treeview()
        layout.addWidget(self.treeView)
        self.setLayout(layout)

    def populate_treeview(self):
        creator = ModeloTreeview(self.icons_dir, self.database_ata_manager)
        model = creator.criar_modelo(self.dataframe)
        self.treeView.setModel(model)
            
class ModeloTreeview:
    def __init__(self, icons_dir, database_ata_manager):
        self.icons = icons_dir
        self.database_ata_manager = database_ata_manager  

    def get_icon_for_cnpj(self, cnpj):
        try:
            query = "SELECT 1 FROM registro_sicaf WHERE cnpj = ?"
            result = self.database_ata_manager.execute_query(query, (cnpj,))
            return self.icons["check"] if result else self.icons["alert"]
        except Exception as e:
            print(f"Modelo Treeview Erro ao acessar o banco de dados: {e}")
            return self.icons["alert"]

    def determinar_itens_iguais(self, row, empresa_items):
        empresa_name = str(row['empresa']) if pd.notna(row['empresa']) else ""
        cnpj = str(row['cnpj']) if pd.notna(row['cnpj']) else ""
        situacao = str(row['situacao']) if pd.notna(row['situacao']) else "Não definido"
        is_situacao_only = not empresa_name and not cnpj
        parent_key = f"{situacao}" if is_situacao_only else f"{cnpj} - {empresa_name}".strip(" -")

        if parent_key not in empresa_items:
            parent_item = QStandardItem()
            parent_item.setEditable(False)
            
            if cnpj:
                icon = self.get_icon_for_cnpj(cnpj)
            else:
                icon = self.icons.get("alert", QIcon())  

            parent_item.setIcon(icon)
            return parent_key, parent_item

        return parent_key, None

    def update_view(self, view):
        view.viewport().update()
        
    def criar_modelo(self, dataframe):
        model, header = self.initializar_modelo(dataframe)
        empresa_items = self.processar_linhas(dataframe, model)
        self.atualizar_contador_cabecalho(empresa_items, model)
        return model

    def initializar_modelo(self, dataframe):
        total_items = len(dataframe)
        situacoes_analizadas = ['Adjudicado e Homologado', 'Fracassado e Homologado', 'Deserto e Homologado', 'Anulado e Homologado', 'Revogado e Homologado']
        nao_analisados = len(dataframe[~dataframe['situacao'].isin(situacoes_analizadas)])
        header = f"Total de itens da licitação {total_items} | Total de itens analisados {total_items - nao_analisados} | Total de itens não analisados {nao_analisados}"
        model = QStandardItemModel()
        model.setHorizontalHeaderLabels([header])
        return model, header

    def processar_linhas(self, dataframe, model):
        empresa_items = {}
        for _, row in dataframe.iterrows():
            self.processar_linhas_individualmente(row, model, empresa_items)
        return empresa_items

    def processar_linhas_individualmente(self, row, model, empresa_items):
        parent_key, parent_item = self.determinar_itens_iguais(row, empresa_items)
        if parent_item:
            model.appendRow(parent_item)
            if parent_key not in empresa_items:
                empresa_items[parent_key] = {
                    'item': parent_item,
                    'count': 0,
                    'details_added': False,
                    'items_container': QStandardItem()  
                }
                empresa_items[parent_key]['items_container'].setEditable(False)

        if parent_key in empresa_items:
            empresa_items[parent_key]['count'] += 1

        self.adicionar_informacao_ao_item(row, empresa_items[parent_key]['item'], empresa_items, parent_key)

    def adicionar_informacao_ao_item(self, row, parent_item, empresa_items, parent_key):
        situacoes_especificas = ['Fracassado e Homologado', 'Deserto e Homologado', 'Anulado e Homologado', 'Revogado e Homologado']
        situacao = row['situacao']

        if situacao not in situacoes_especificas and situacao != 'Adjudicado e Homologado':
            situacao = 'Não definido'

        if situacao in situacoes_especificas or situacao == 'Não definido':
            item_text = f"Item {row['item']} - {row['descricao']} - {situacao}"
            item_info = QStandardItem(item_text)
            item_info.setEditable(False)
            parent_item.appendRow(item_info)
        else:
            self.adicionar_subitens_detalhados(row, empresa_items[parent_key]['items_container'])

        item_count_text = "Item" if empresa_items[parent_key]['count'] == 1 else "Relação de itens:"
        empresa_items[parent_key]['items_container'].setText(f"{item_count_text} ({empresa_items[parent_key]['count']})")
        
    def atualizar_contador_cabecalho(self, empresa_items, model):
        for chave_item_pai, empresa in empresa_items.items():
            count = empresa['count']
            display_text = f"{chave_item_pai} (1 item)" if count == 1 else f"{chave_item_pai} ({count} itens)"
            empresa['item'].setText(display_text)

    def adicionar_detalhes_empresa(self, row, parent_item):
        infos = [
            f"Endereço: {row['endereco']}, CEP: {row['cep']}, Município: {row['municipio']}" if pd.notna(row['endereco']) else "Endereço: Não informado",
            f"Contato: {row['telefone']} Email: {row['email']}" if pd.notna(row['telefone']) else "Contato: Não informado",
            f"Responsável Legal: {row['responsavel_legal']}" if pd.notna(row['responsavel_legal']) else "Responsável Legal: Não informado"
        ]
        for info in infos:
            info_item = QStandardItem(info)
            info_item.setEditable(False)
            parent_item.appendRow(info_item)

    def criar_dados_sicaf_do_item(self, row):
        fields = ['endereco', 'cep', 'municipio', 'telefone', 'email', 'responsavel_legal']
        return [self.criar_detalhe_item(field.capitalize(), row[field]) for field in fields if pd.notna(row[field])]

    def adicionar_subitens_detalhados(self, row, sub_items_layout):
        item_info_html = f"Item {row['item']} - {row['descricao']} - {row['situacao']}"
        item_info = QStandardItem(item_info_html)
        item_info.setEditable(False)
        sub_items_layout.appendRow(item_info)

        detalhes = [
            f"Descrição Detalhada: {row['descricao_detalhada']}",
            f"Unidade de Fornecimento: {row.get('unidade', 'Não informado')} Quantidade: {self.formatar_quantidade(row['quantidade'])} "
            f"Valor Estimado: {self.formatar_brl(row['valor_estimado'])} Valor Homologado: {self.formatar_brl(row['valor_homologado_item_unitario'])} "
            f"Desconto: {self.formatar_percentual(row['percentual_desconto'])} Marca: {row['marca_fabricante']} Modelo: {row['modelo_versao']}",
        ]

        for detalhe in detalhes:
            detalhe_item = QStandardItem(detalhe)
            detalhe_item.setEditable(False)
            item_info.appendRow(detalhe_item)

    def criar_detalhe_item(self, label, data):
        return QStandardItem(f"<b>{label}:</b> {data if pd.notna(data) else 'Não informado'}")

    def formatar_brl(self, valor):
        try:
            if valor is None or pd.isna(valor):
                return "Não disponível"  
            return f"R$ {float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        except ValueError:
            return "Valor inválido"

    def formatar_quantidade(self, valor):
        try:
            if pd.isna(valor): return "0"
            float_value = float(valor)
            if float_value.is_integer():
                return f"{int(float_value)}"
            else:
                return f"{float_value:.2f}".replace('.', ',')
        except ValueError:
            return "Erro de Formatação"

    def formatar_percentual(self, valor):
        try:
            if pd.isna(valor): return "0,00%"
            percent_value = float(valor)
            return f"{percent_value:.2f}%"
        except ValueError:
            return "Erro de Formatação"

class WorkerSICAF(QThread):
    processing_complete = pyqtSignal(list)  
    update_context_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(int)

    def __init__(self, sicaf_dir, parent=None):
        super().__init__(parent)
        self.sicaf_dir = sicaf_dir

    def run(self):
        dataframes = []
        pdf_files = list(self.sicaf_dir.glob("*.pdf"))
        total_files = len(pdf_files)

        for index, pdf_file in enumerate(pdf_files):
            text = self.process_single_pdf(pdf_file)
            if text:
                df_sicaf = extrair_dados_sicaf(text)
                df_responsavel = extrair_dados_responsavel(text)
                
                if not df_sicaf.empty or not df_responsavel.empty:
                    df_combined = pd.concat([df_sicaf, df_responsavel], axis=1)
                    dataframes.append(df_combined)
                    self.update_context_signal.emit(f"Análise do PDF {pdf_file.name} concluída com êxito.")
                else:
                    self.update_context_signal.emit(f"Nenhum dado extraído de {pdf_file.name}.")
            else:
                self.update_context_signal.emit(f"Não foi possível obter os dados corretamente de {pdf_file.name}.")

            progress = int((index + 1) / total_files * 100)
            self.progress_signal.emit(progress)
            QThread.msleep(1)  

        self.processing_complete.emit(dataframes)

    def process_single_pdf(self, pdf_file):
        try:
            with pdfplumber.open(pdf_file) as pdf:
                text = ""
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
                    else:
                        self.update_context_signal.emit(f"Aviso: Página de {pdf_file.name} não contém texto extraível.")
                return text
        except Exception as e:
            self.update_context_signal.emit(f"Erro ao processar {pdf_file.name}: {e}")
            return None


def extrair_dados_sicaf(texto: str) -> pd.DataFrame:
    dados_sicaf = (
        r"CNPJ:\s*(?P<cnpj>[\d./-]+)\s*"
        r"(?:DUNS®:\s*(?P<duns>[\d]+)\s*)?"
        r"Razão Social:\s*(?P<empresa>.*?)\s*"
        r"Nome Fantasia:\s*(?P<nome_fantasia>.*?)\s*"
        r"Situação do Fornecedor:\s*(?P<situacao_cadastro>.*?)\s*"
        r"Data de Vencimento do Cadastro:\s*(?P<data_vencimento>\d{2}/\d{2}/\d{4})\s*"
        r".*?CEP:\s*(?P<cep>[\d.-]+)\s*"
        r"Endereço:\s*(?P<endereco>.*?)\s*"
        r"Município\s*/\s*UF:\s*(?P<municipio>[^/]+?)\s*/\s*(?P<uf>.*?)(?=\s*(?:Telefone:|E-mail:|Dados do Responsável|$|\n|\r))\s*"
        r"(?:Telefone:\s*(?P<telefone>[^\n\r]+?)(?=\s*(?:E-mail:|Dados do Responsável|$|\n|\r))\s*)?"
        r"(?:E-mail:\s*(?P<email>[^\n\r]+?)(?=\s*(?:Dados do Responsável|$|\n|\r))\s*)?"
    )

    match = re.search(dados_sicaf, texto, re.S | re.IGNORECASE)
    if not match:
        return pd.DataFrame()  

    data = {key: [value.strip()] if value else [None] for key, value in match.groupdict().items()}
    return pd.DataFrame(data)

def extrair_dados_responsavel(texto: str) -> pd.DataFrame:
    dados_responsavel_sicaf = (
        r"Dados do Responsável Legal\s*CPF:\s*(?P<cpf>\d{3}\.\d{3}\.\d{3}-\d{2})\s*Nome:\s*"
        r"(?P<nome>[^\n\r]*?)(?:\s*Dados do Responsável pelo Cadastro|\s*Emitido em:|\s*CPF:|$)"
    )

    match = re.search(dados_responsavel_sicaf, texto, re.S)
    if not match:
        return pd.DataFrame()  

    data = {key: [value.strip()] if value else [None] for key, value in match.groupdict().items()}
    return pd.DataFrame(data)

padrao_1 = (r"UASG\s+(?P<uasg>\d+)\s+-\s+(?P<orgao_responsavel>.+?)\s+PREGÃO\s+(?P<num_pregao>\d+)/(?P<ano_pregao>\d+)")
padrao_srp = r"(?P<srp>SRP - Registro de Preço|SISPP - Tradicional)"
padrao_objeto = (r"Objeto da compra:\s*(?P<objeto>.*?)\s*Entrega de propostas:")

padrao_grupo2 = (
    r"Item\s+(?P<item>\d+)(?:\s+do\s+Grupo\s+G(?P<grupo>\d+))?.*?"
    r"Valor\s+estimado:\s+R\$\s+(?P<valor>[\d,\.]+).*?"
    r"(?:Critério\s+de\s+julgamento:\s+(?P<crit_julgamento>.*?))?\s*"
    r"Quantidade:\s+(?P<quantidade>\d+)\s+"
    r"(?:Unidade\s+de\s+fornecimento|UF):\s+(?P<unidade>.*?)(?=\s*R\$|\s*Situação:)\s*.*?"
    r"Situação:\s+(?P<situacao>Adjudicado e Homologado|Deserto e Homologado|Fracassado e Homologado|Anulado e Homologado|Revogado e Homologado)"
)

padrao_item_quantidade = (
    r"Item\s+(?P<item>\d+)\s+-\s+.*?"
    r"Quantidade:\s+(?P<quantidade>\d+)\s+"
)

padrao_valor_estimado_unidade_fornecimento = (
    r"Valor\s+estimado:\s+R\$\s+(?P<valor>[\d,.]+)(?:\s+\(unitário\))?\s+"
    r"(?:Unidade\s+de\s+fornecimento|UF):\s+(?P<unidade>.*?)(?=\s*R\$|\s*Situação:)\s*.*?"
)

padrao_situacao = (
    r"Situação:\s+(?P<situacao>"
    r"Adjudicado e Homologado|Deserto e Homologado|Fracassado e Homologado|Anulado e Homologado|Revogado e Homologado)"
)

padrao_item2 = padrao_item_quantidade + padrao_valor_estimado_unidade_fornecimento + padrao_situacao

padrao_4 = (
    r"Proposta\s+adjudicada.*?"
    r"Marca/Fabricante\s*:\s*(?P<marca_fabricante>.*?)\s*"
    r"Modelo/versão\s*:\s*(?P<modelo_versao>.*?)(?=\s*\d{2}/\d{2}/\d{4}|\s*Valor\s+proposta\s*:)"
)

padrao_cpf_od = (
    r"(?:Adjucado|Adjudicado)\s+e\s+Homologado\s+por\s+CPF\s+"
    r"(?P<cpf_od>\*\*\*.\d{3}.\*\*\*-\*\d{1})\s+-\s+"
    r"(?P<ordenador_despesa>[^\d,]+?)\s+para\s+"
)

padrao_empresa = (
    r"(?P<empresa>.*?)(?=\s*,\s*CNPJ\s+)"
    r"\s*,\s*CNPJ\s+(?P<cnpj>\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}),\s+"
)

padrao_bloco_valores = (
    r"(?P<bloco_valores>.*?)(?=\s*Propostas\s+do\s+Item)"
)

padrao_3 = padrao_cpf_od + padrao_empresa + padrao_bloco_valores


def processar_item(match, conteudo: str, ultima_posicao_processada: int, padrao_3: str, padrao_4: str) -> dict:
    item = match.groupdict()
    
    # =================================================================
    # CORREÇÃO DEFINITIVA DA UNIDADE: 
    # Adicionado re.DOTALL para forçar a limpeza ignorando quebras de linha!
    # =================================================================
    unidade_bruta = str(item.get('unidade', 'N/A'))
    unidade_limpa = re.sub(r'\s*R\$.*', '', unidade_bruta, flags=re.DOTALL | re.IGNORECASE).strip()

    item_data = {
        "item": int(item['item']) if 'item' in item and item['item'].isdigit() else 'N/A',
        "grupo": item.get('grupo', 'N/A'),
        "valor_estimado": item.get('valor', 'N/A'),
        "quantidade": item.get('quantidade', 'N/A'),
        "unidade": unidade_limpa,
        "situacao": item.get('situacao', 'N/A')
    }

    if item_data['situacao'] == 'Adjudicado e Homologado':
        match_3 = re.search(padrao_3, conteudo, re.DOTALL | re.IGNORECASE)
        
        if match_3:
            item_data["ordenador_despesa"] = match_3.group('ordenador_despesa').strip()
            item_data["empresa"] = match_3.group('empresa').replace('\n', ' ').strip()
            item_data["cnpj"] = match_3.group('cnpj').strip()

            bloco_valores = match_3.group('bloco_valores')
            
            match_lance = re.search(r"melhor\s+lance\s*:\s*R\$\s*([\d,.]+)", bloco_valores)
            item_data["melhor_lance"] = match_lance.group(1) if match_lance else 'N/A'

            match_negociado = re.search(r"valor\s+negociado\s*:\s*R\$\s*([\d,.]+)", bloco_valores)
            item_data["valor_negociado"] = match_negociado.group(1) if match_negociado else 'N/A'
            
            posicao_final_match_3 = match_3.end()
            match_4 = re.search(padrao_4, conteudo[posicao_final_match_3:], re.DOTALL | re.IGNORECASE)
            if match_4:
                item_data["marca_fabricante"] = match_4.group('marca_fabricante').strip() or 'N/A'
                item_data["modelo_versao"] = match_4.group('modelo_versao').strip() or 'N/A'

    return item_data, ultima_posicao_processada 

def create_dataframe_from_pdf_files(extracted_data):
    if not isinstance(extracted_data, list):
        raise TypeError("extracted_data deve ser uma lista de dicionários.")

    all_data = []
    print("\nIniciando processamento de extracted_data...\n")

    for idx, item in enumerate(extracted_data):
        if isinstance(item, dict) and 'text' in item and isinstance(item['text'], str):
            content = item['text']
            
            uasg_pregao_data = extrair_uasg_e_pregao(content, padrao_1, padrao_srp, padrao_objeto)
            compra_data = extrair_objeto_da_compra(content)
            items_data = identificar_itens_e_grupos(content, padrao_grupo2, padrao_item2, padrao_3, padrao_4, pd.DataFrame())

            for item_data in items_data:
                if isinstance(item_data, dict):
                    all_data.append({
                        **uasg_pregao_data,
                        "objeto": compra_data,  
                        **item_data
                    })
                else:
                    print(f"Formato inesperado em item_data: {item_data}")
        else:
            print(f"Formato inválido em extracted_data: {item} (Tipo: {type(item)})")

    if not all_data:
        raise ValueError("Nenhum dado válido foi encontrado para criar o DataFrame.")

    dataframe_licitacao = pd.DataFrame(all_data)
    
    if "item" not in dataframe_licitacao.columns:
        raise ValueError("A coluna 'item' não foi encontrada no DataFrame.")
    
    return dataframe_licitacao.sort_values(by="item")

def identificar_itens_e_grupos(conteudo: str, padrao_grupo2: str, padrao_item2: str, padrao_3: str, padrao_4: str, df: pd.DataFrame) -> list:
    conteudo = re.sub(r'\s+', ' ', conteudo).strip()
    itens_data = []
    itens = buscar_itens(conteudo, padrao_grupo2, padrao_item2)

    ultima_posicao_processada = 0
    for idx, match in enumerate(itens):
        item_data, ultima_posicao_processada = processar_item(match, conteudo, ultima_posicao_processada, padrao_3, padrao_4)
        item_data = process_cnpj_data(item_data)
        itens_data.append(item_data)

    return itens_data

def process_cnpj_data(cnpj_dict):
    for field in ["valor_estimado", "melhor_lance", "valor_negociado"]:
        valor = cnpj_dict.get(field, 'N/A')  
        if isinstance(valor, str):
            try:
                cnpj_dict[field] = float(valor.replace(".", "").replace(",", "."))
            except ValueError:
                cnpj_dict[field] = 'N/A'

    quantidade = cnpj_dict.get("quantidade", 'N/A')
    try:
        cnpj_dict["quantidade"] = int(quantidade)
    except ValueError:
        pass

    valor_negociado = cnpj_dict.get("valor_negociado", 'N/A')
    if valor_negociado in [None, "N/A", "", "none", "null"]:
        cnpj_dict["valor_homologado_item_unitario"] = cnpj_dict.get("melhor_lance", 'N/A')
    else:
        cnpj_dict["valor_homologado_item_unitario"] = valor_negociado

    valor_estimado = cnpj_dict.get("valor_estimado", 'N/A')
    valor_homologado_item_unitario = cnpj_dict.get("valor_homologado_item_unitario", 'N/A')
    if valor_estimado != 'N/A' and valor_homologado_item_unitario != 'N/A':
        try:
            cnpj_dict["valor_estimado_total_do_item"] = cnpj_dict["quantidade"] * float(valor_estimado)
            cnpj_dict["valor_homologado_total_item"] = cnpj_dict["quantidade"] * float(valor_homologado_item_unitario)
            cnpj_dict["percentual_desconto"] = (1 - (float(valor_homologado_item_unitario) / float(valor_estimado))) * 100
        except ValueError:
            pass
            
    return cnpj_dict

def buscar_itens(conteudo: str, padrao_grupo2: str, padrao_item2: str) -> list:
    conteudo = re.sub(r'\s+', ' ', conteudo).strip()

    matches_item2 = list(re.finditer(padrao_item2, conteudo, re.DOTALL | re.IGNORECASE))
    if matches_item2:
        return matches_item2  

    matches_grupo2 = list(re.finditer(padrao_grupo2, conteudo, re.DOTALL | re.IGNORECASE))
    if matches_grupo2:
        return matches_grupo2  

    return []  

def extrair_objeto_da_compra(conteudo: str) -> str:
    padrao_objeto_forte = r"Objeto\s+da\s+compra\s*:\s*(?P<objeto>.*?)\s*Entrega\s+de\s+propostas\s*:"
    match = re.search(padrao_objeto_forte, conteudo, re.DOTALL | re.IGNORECASE)

    if match:
        return match.group("objeto").strip()
    else:
        return "N/A"
    
def extrair_uasg_e_pregao(conteudo: str, padrao_1: str, padrao_srp: str, padrao_objeto: str) -> dict: 
    match = re.search(padrao_1, conteudo)
    match2 = re.search(padrao_srp, conteudo)
    match3 = re.search(padrao_objeto, conteudo)

    srp_valor = match2.group("srp") if match2 else "N/A"
    objeto_valor = match3.group("objeto") if match3 else "N/A"

    if not match3:
        padrao_objeto_forte = r"Objeto\s+da\s+compra\s*:\s*(?P<objeto>.*?)\s*Entrega\s+de\s+propostas\s*:"
        match_forte = re.search(padrao_objeto_forte, conteudo, re.DOTALL | re.IGNORECASE)
        if match_forte:
            objeto_valor = match_forte.group("objeto").strip()

    if match:
        return {
            "uasg": match.group("uasg"),
            "orgao_responsavel": match.group("orgao_responsavel"),
            "num_pregao": match.group("num_pregao"),
            "ano_pregao": match.group("ano_pregao"),
            "srp": srp_valor,
            "objeto": objeto_valor
        }
    return {}

def save_to_dataframe(extracted_data): 
    df_extracted = create_dataframe_from_pdf_files(extracted_data)
    df_extracted['item'] = pd.to_numeric(df_extracted['item'], errors='coerce').astype('Int64')
    return df_extracted