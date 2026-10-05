import os
import pandas as pd
import fitz
import re
import openpyxl
from openpyxl.styles import Font
from pathlib import Path
from PyQt6.QtWidgets import *
from PyQt6.QtGui import *
from PyQt6.QtCore import *
from modules.utils.add_button import add_button

class AlertaFaltaDelegate(QStyledItemDelegate):
    def paint(self, painter, option, index):
        texto = str(index.data(Qt.ItemDataRole.DisplayRole) or "")
        if "Preencha manualmente" in texto:
            opt = QStyleOptionViewItem(option)
            self.initStyleOption(opt, index)
            opt.text = "" 
            super().paint(painter, opt, index) 
            
            painter.save()
            font = opt.font
            font.setBold(True)
            painter.setFont(font)
            painter.setPen(QColor("red")) 
            rect = opt.rect
            rect.adjust(5, 0, -5, 0)
            alinhamento = Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft
            painter.drawText(rect, alinhamento, texto)
            painter.restore()
        else:
            super().paint(painter, option, index)

# =================================================================
# DIÁLOGO DE CONFIGURAÇÃO DE EXTRAÇÃO (OPÇÃO 1 E OPÇÃO 2)
# =================================================================
class ConfigExtracaoDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Configuração da Extração do TR")
        self.resize(550, 500)
        layout = QVBoxLayout(self)

        lbl_expl = QLabel("Para que a extração funcione na opção 1, o TR deve seguir o seguinte padrão:\n(Item, Descrição, Especificação, CATMAT ou CATSER)")
        lbl_expl.setWordWrap(True)
        lbl_expl.setStyleSheet("font-weight: bold; font-size: 13px; color: #2C3E50; background-color: #E8F8F5; padding: 10px; border-radius: 5px;")
        layout.addWidget(lbl_expl)

        self.rb_opcao1 = QRadioButton("Opção 1: Extração Padrão Automática")
        self.rb_opcao1.setFont(QFont('Arial', 11, QFont.Weight.Bold))
        self.rb_opcao1.setChecked(True)
        layout.addWidget(self.rb_opcao1)

        linha = QFrame()
        linha.setFrameShape(QFrame.Shape.HLine)
        linha.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(linha)

        self.rb_opcao2 = QRadioButton("Opção 2: Personalizar nomes das colunas")
        self.rb_opcao2.setFont(QFont('Arial', 11, QFont.Weight.Bold))
        layout.addWidget(self.rb_opcao2)
        
        lbl_op2_desc = QLabel("Caso o TR junte a Descrição e a Especificação numa só coluna, digite abaixo os cabeçalhos exatos que o seu PDF possui. O sistema buscará essas colunas isoladamente. (Dica: Deixe em branco as colunas que mantiveram o nome padrão, ex: 'Item' ou 'CATMAT')")
        lbl_op2_desc.setWordWrap(True)
        lbl_op2_desc.setStyleSheet("color: #555555;")
        layout.addWidget(lbl_op2_desc)

        self.custom_container = QWidget()
        form_layout = QFormLayout(self.custom_container)
        
        self.input_item = QLineEdit()
        self.input_item.setPlaceholderText("Deixe em branco para usar o padrão (Item, Nº)")
        form_layout.addRow("Coluna do Item:", self.input_item)

        self.input_cat = QLineEdit()
        self.input_cat.setPlaceholderText("Deixe em branco para usar o padrão (CATMAT, Código)")
        form_layout.addRow("Coluna do Catálogo:", self.input_cat)

        self.input_desc = QLineEdit()
        self.input_desc.setPlaceholderText("Ex: Nome, Objeto, Descrição")
        form_layout.addRow("Coluna da Descrição (Curta):", self.input_desc)

        self.input_desc_det = QLineEdit()
        self.input_desc_det.setPlaceholderText("Ex: Detalhamento, Especificação")
        form_layout.addRow("Coluna da Especificação:", self.input_desc_det)

        self.custom_container.setEnabled(False)
        layout.addWidget(self.custom_container)

        self.rb_opcao1.toggled.connect(lambda: self.custom_container.setEnabled(not self.rb_opcao1.isChecked()))

        layout.addStretch()

        botoes = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        botoes.accepted.connect(self.accept)
        botoes.rejected.connect(self.reject)
        layout.addWidget(botoes)
    
    def get_config(self):
        return {
            'opcao': 1 if self.rb_opcao1.isChecked() else 2,
            'col_item': self.input_item.text().strip().lower() or 'item',
            'col_cat': self.input_cat.text().strip().lower() or 'catmat',
            'col_desc': self.input_desc.text().strip().lower() or 'descrição',
            'col_desc_det': self.input_desc_det.text().strip().lower() or 'especificação'
        }


class TermoReferenciaWidget(QWidget): 
    abrirTabelaNova = pyqtSignal()
    carregarTabela = pyqtSignal()  
    configurarSqlModelSignal = pyqtSignal() 
    extrairTrSignal = pyqtSignal() 

    def __init__(self, parent, icons):
        super().__init__(parent)
        self.setWindowTitle("Termo de Referência")
        self.resize(800, 600)
        self.parent = parent
        self.icons = icons
        
        self.layout = QVBoxLayout(self)
        title_layout = QHBoxLayout()
        title_layout.addStretch()
        
        title = QLabel("Especificação do Termo de Referência")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setFont(QFont('Arial', 16, QFont.Weight.Bold))
        title_layout.addWidget(title)

        add_button("Tabela em Branco", "excel_down", self.abrirTabelaNova, title_layout, self.icons, tooltip="Cria uma tabela vazia", button_size=(180, 30))
        add_button("Extrair TR para Excel", "pdf", self.extrairTrSignal, title_layout, self.icons, tooltip="Extrai as especificações do PDF", button_size=(200, 30))
        self.extrairTrSignal.connect(self.abrir_dialog_config_extracao)
        add_button("Carregar Tabela", "excel_up", self.carregarTabela, title_layout, self.icons, tooltip="Carrega a tabela preenchida para o banco", button_size=(180, 30))
        
        title_layout.addStretch()
        self.layout.addLayout(title_layout)
        
        title1 = QLabel("Extraia as especificações automaticamente para Excel, corrija os itens em vermelho, e carregue a tabela concluída.")
        title1.setAlignment(Qt.AlignmentFlag.AlignLeft)
        title1.setFont(QFont('Arial', 12))
        self.layout.addWidget(title1)

        title2 = QLabel("Importante! O índice da tabela deve ser 'item', 'catalogo', 'descricao' e 'descricao_detalhada'.")
        title2.setAlignment(Qt.AlignmentFlag.AlignLeft)
        title2.setFont(QFont('Arial', 12))
        self.layout.addWidget(title2)

        self.table_view = QTableView(self)
        self.table_view.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)  
        self.table_view.verticalHeader().setVisible(False)  
        
        self.delegado_alerta = AlertaFaltaDelegate(self)
        self.table_view.setItemDelegate(self.delegado_alerta)
        self.layout.addWidget(self.table_view)

        self.table_view.setStyleSheet("""
            QTableView { background-color: #F3F3F3; color: #333333; gridline-color: #CCCCCC; font-size: 14px;}
            QTableView::item:selected { background-color: #E0E0E0; color: #000000; }
            QTableView::item { border: 1px solid transparent; padding: 5px; }
            QHeaderView::section { background-color: #D6D6D6; color: #333333; font-weight: bold; font-size: 14px; padding: 4px; border: 1px solid #CCCCCC; }
        """)

        self.configurarSqlModelSignal.emit()

    def abrir_dialog_config_extracao(self):
        dialog = ConfigExtracaoDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            config = dialog.get_config()
            self.extrairPdfParaExcel(config)

    # =================================================================
    # O DETETIVE DE LIXO DE CABEÇALHO (MATA "DE MEDIDA", "TOTAL R$", ETC)
    # =================================================================
    def _is_header_artifact(self, text):
        if not text: return True
        t = str(text).lower()
        t = t.replace("(r$)", "").replace("r$", "").replace("%", "")
        t = re.sub(r'[^\w\s]', ' ', t) # Transforma pontuação em espaço
        
        # Lista de lixos conhecidos que vazam das colunas
        words = [
            "de", "medida", "min", "mín", "max", "máx", "total", "unitario", "unitário", 
            "unidade", "quant", "quantidade", "valor", "situacao", "situação", 
            "item", "nº", "catmat", "catser", "codigo", "código", "descricao", "descrição", 
            "especificacao", "especificação", "objeto", "nome", "minimo", "mínimo", "maximo", "máximo",
            "un", "und", "kg", "cx", "pc", "pct", "estimado", "referencia", "referência",
            "marca", "fabricante", "modelo", "versao", "versão", "proposta", "fornecimento"
        ]
        # Pulveriza as palavras indesejadas
        for w in words:
            t = re.sub(r'\b' + w + r'\b', ' ', t)
            
        # Se depois de apagar as palavras de cabeçalho não sobrar nada válido, é LIXO!
        return len(t.strip()) == 0

    def extrairPdfParaExcel(self, config):
        dir_seguro = os.path.expanduser("~")
        pdf_path, _ = QFileDialog.getOpenFileName(self, "Selecione o PDF do Termo de Referência", dir_seguro, "Arquivos PDF (*.pdf)")
        if not pdf_path: return

        save_path, _ = QFileDialog.getSaveFileName(self, "Onde deseja salvar a Planilha Preenchida?", os.path.join(dir_seguro, "TR_Extraido.xlsx"), "Excel (*.xlsx)")
        if not save_path: return

        loading = QProgressDialog("Lendo o PDF e gerando o Excel...\nIsso pode levar alguns segundos.", None, 0, 0, self)
        loading.setWindowTitle("Processando")
        loading.setWindowModality(Qt.WindowModality.WindowModal)
        loading.setMinimumDuration(0)
        loading.setCancelButton(None)
        loading.show()
        QApplication.processEvents()

        try:
            df = self._processar_extracao(pdf_path, config)
            
            if df.empty:
                QMessageBox.warning(self, "Aviso", "Não foi possível extrair os itens deste PDF com a configuração selecionada.")
                return
            
            df.to_excel(save_path, index=False)
            
            # Pinta as células com problemas
            wb = openpyxl.load_workbook(save_path)
            ws = wb.active
            fonte_vermelha = Font(color="FF0000", bold=True)
            for row in ws.iter_rows():
                for cell in row:
                    if cell.value == "Preencha manualmente":
                        cell.font = fonte_vermelha
            wb.save(save_path)

            QMessageBox.information(self, "Sucesso", f"Planilha gerada com sucesso em:\n{save_path}\n\n1. Abra o arquivo Excel.\n2. Corrija as linhas em vermelho.\n3. Salve o arquivo e clique em 'Carregar Tabela'.")
        
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Ocorreu um erro durante a extração:\n{str(e)}")
        finally:
            loading.close()

    def _processar_extracao(self, pdf_path, config):
        import pdfplumber
        linhas_brutas = []
        termos_rodape = [
            "manual de modelos", "consultoria-geral", "consultoria geral", 
            "da união", "secretaria de gestão", "atualização:", "atualiz", 
            "câmara nacional", "licitações e contratos"
        ]
        
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                tables = page.extract_tables()
                if not tables: continue
                for table in tables:
                    for row in table:
                        if not any(row): continue
                        max_lines = 1
                        for cell in row:
                            if cell:
                                linhas_celula = str(cell).split('\n')
                                if len(linhas_celula) > max_lines: max_lines = len(linhas_celula)
                        for i in range(max_lines):
                            new_row = []
                            for cell in row:
                                if not cell: new_row.append("")
                                else:
                                    linhas_celula = str(cell).split('\n')
                                    if i < len(linhas_celula): new_row.append(linhas_celula[i].strip())
                                    else: new_row.append("")
                            if any(new_row): linhas_brutas.append(new_row)

        lista_dados = []

        # =================================================================
        # OPÇÃO 1: Extração Padrão Automática
        # =================================================================
        if config['opcao'] == 1:
            dados = {}
            current_item = None
            orphan_cat = ""
            orphan_desc = ""
            orphan_spec = ""

            for row in linhas_brutas:
                row_clean = [str(c).replace('\n', ' ').strip() for c in row]
                texto_linha = " ".join(row_clean).lower()
                
                if 'item' in str(row_clean[0]).lower() or ('descrição' in texto_linha and 'especificação' in texto_linha): 
                    continue

                r_item = ""
                primeira_celula = re.sub(r'[^\d]', '', row_clean[0])
                if primeira_celula and row_clean[0].strip() == primeira_celula: 
                    r_item = primeira_celula
                    current_item = str(int(r_item))

                if any(termo in texto_linha for termo in termos_rodape):
                    if current_item:
                        if current_item not in dados: dados[current_item] = {}
                        dados[current_item]["catalogo"] = "Preencha manualmente"
                        dados[current_item]["descricao"] = "Preencha manualmente"
                        dados[current_item]["descricao_detalhada"] = "Preencha manualmente"
                    continue 

                if current_item in dados and dados[current_item].get("descricao") == "Preencha manualmente":
                    continue

                r_cat = ""
                spec_parts = []

                for i, cell in enumerate(row_clean):
                    if i == 0 and r_item: continue 
                    if not cell: continue

                    limpo_cat = re.sub(r'[^\d]', '', cell)
                    if not r_cat and len(limpo_cat) >= 5 and len(limpo_cat) <= 7 and re.fullmatch(r'\d{5,7}', limpo_cat):
                        if len(cell) <= 12: 
                            r_cat = limpo_cat
                            continue
                    
                    if re.fullmatch(r'\d{1,4}', cell) or re.fullmatch(r'\d{1,3}(?:\.\d{3})*(?:,\d{2})', cell): continue
                    
                    # FILTRA O LIXO DO CABEÇALHO PARA NÃO ENTRAR NA DESCRIÇÃO!
                    if self._is_header_artifact(cell):
                        continue
                        
                    spec_parts.append(cell)

                r_desc = ""
                r_spec = ""
                if len(spec_parts) == 1:
                    r_spec = spec_parts[0]
                elif len(spec_parts) > 1:
                    r_desc = spec_parts[0]
                    r_spec = " ".join(spec_parts[1:])

                if r_item:
                    if current_item not in dados: dados[current_item] = {"catalogo": "", "descricao": "", "descricao_detalhada": ""}
                    if orphan_cat: dados[current_item]["catalogo"] = orphan_cat; orphan_cat = ""
                    if orphan_desc: dados[current_item]["descricao"] += (" " + orphan_desc); orphan_desc = ""
                    if orphan_spec: dados[current_item]["descricao_detalhada"] += (" " + orphan_spec); orphan_spec = ""
                    
                    if r_cat: dados[current_item]["catalogo"] = r_cat
                    if r_desc: dados[current_item]["descricao"] += (" " + r_desc.strip())
                    if r_spec: dados[current_item]["descricao_detalhada"] += (" " + r_spec.strip())
                else: 
                    if current_item:
                        if r_cat: dados[current_item]["catalogo"] = r_cat
                        if r_desc: dados[current_item]["descricao"] += (" " + r_desc.strip())
                        if r_spec: dados[current_item]["descricao_detalhada"] += (" " + r_spec.strip())
                    else:
                        if r_cat: orphan_cat = r_cat
                        if r_desc: orphan_desc += (" " + r_desc)
                        if r_spec: orphan_spec += (" " + r_spec)

            for k, v in dados.items():
                lista_dados.append({
                    "item": k,
                    "catalogo": v["catalogo"],
                    "descricao": " ".join(v["descricao"].split()),
                    "descricao_detalhada": " ".join(v["descricao_detalhada"].split())
                })

        # =================================================================
        # OPÇÃO 2: Extração Baseada nos Cabeçalhos do Utilizador
        # =================================================================
        elif config['opcao'] == 2:
            header_mapped = False
            idx_item, idx_cat, idx_desc, idx_desc_det = -1, -1, -1, -1
            
            for row in linhas_brutas:
                row_clean = [str(c).replace('\n', ' ').strip() for c in row]
                row_lower = [c.lower() for c in row_clean]
                
                if not header_mapped:
                    matches = 0
                    for i, cell_val in enumerate(row_lower):
                        matched_any = False
                        if config['col_item'] in cell_val: idx_item = i; matched_any = True
                        if config['col_cat'] in cell_val: idx_cat = i; matched_any = True
                        if config['col_desc'] in cell_val: idx_desc = i; matched_any = True
                        if config['col_desc_det'] in cell_val: idx_desc_det = i; matched_any = True
                        if matched_any: matches += 1
                        
                if not header_mapped and idx_item != -1 and matches >= 2:
                    header_mapped = True
                    continue
                
                if header_mapped:
                    if not any(row_clean): continue
                    
                    v_item = row_clean[idx_item] if idx_item != -1 and idx_item < len(row_clean) else ""
                    v_cat = row_clean[idx_cat] if idx_cat != -1 and idx_cat < len(row_clean) else ""
                    v_desc = row_clean[idx_desc] if idx_desc != -1 and idx_desc < len(row_clean) else ""
                    v_desc_det = row_clean[idx_desc_det] if idx_desc_det != -1 and idx_desc_det < len(row_clean) else ""
                    
                    v_item_limpo = re.sub(r'[^\d]', '', v_item)
                    texto_linha = " ".join(row_clean).lower()
                    
                    if any(termo in texto_linha for termo in termos_rodape):
                        if v_item_limpo: 
                            lista_dados.append({
                                "item": v_item_limpo,
                                "catalogo": "Preencha manualmente",
                                "descricao": "Preencha manualmente",
                                "descricao_detalhada": "Preencha manualmente"
                            })
                        else:
                            if lista_dados:
                                lista_dados[-1]["catalogo"] = "Preencha manualmente"
                                lista_dados[-1]["descricao"] = "Preencha manualmente"
                                lista_dados[-1]["descricao_detalhada"] = "Preencha manualmente"
                        continue

                    # FILTRA O LIXO ANTES DE ADICIONAR
                    if self._is_header_artifact(v_desc): v_desc = ""
                    if self._is_header_artifact(v_desc_det): v_desc_det = ""

                    if v_item_limpo: 
                        lista_dados.append({
                            "item": v_item_limpo,
                            "catalogo": v_cat,
                            "descricao": v_desc,
                            "descricao_detalhada": v_desc_det
                        })
                    else:
                        if lista_dados:
                            if lista_dados[-1]["descricao"] != "Preencha manualmente":
                                if v_cat and not self._is_header_artifact(v_cat): lista_dados[-1]["catalogo"] += " " + v_cat
                                if v_desc: lista_dados[-1]["descricao"] += " " + v_desc
                                if v_desc_det: lista_dados[-1]["descricao_detalhada"] += " " + v_desc_det

        df = pd.DataFrame(lista_dados)
        if df.empty: return df
        
        for col in ['item', 'catalogo', 'descricao', 'descricao_detalhada']:
            if col not in df.columns: df[col] = ""

        # PREENCHE OS BURACOS GERADOS PELA LIMPEZA DO LIXO
        for col in ['catalogo', 'descricao', 'descricao_detalhada']:
            df[col] = df[col].apply(lambda x: 'Preencha manualmente' if pd.isna(x) or str(x).strip() == '' else x)

        # AUDITOR DE PULO DE NÚMEROS
        df['temp_item'] = pd.to_numeric(df['item'], errors='coerce')
        if not df['temp_item'].isna().all():
            maior_item = int(df['temp_item'].max())
            itens_encontrados = set(df.dropna(subset=['temp_item'])['temp_item'].astype(int).tolist())
            
            linhas_injetadas = []
            for i in range(1, maior_item + 1):
                if i not in itens_encontrados:
                    linhas_injetadas.append({
                        'item': str(i),
                        'catalogo': 'Preencha manualmente',
                        'descricao': 'Preencha manualmente',
                        'descricao_detalhada': 'Preencha manualmente'
                    })
            
            if linhas_injetadas:
                df_missing = pd.DataFrame(linhas_injetadas)
                df = pd.concat([df, df_missing], ignore_index=True)
                df['temp_item'] = pd.to_numeric(df['item'], errors='coerce').fillna(99999)
                df = df.sort_values('temp_item').reset_index(drop=True)
        
        df = df.drop(columns=['temp_item'], errors='ignore')
        return df[['item', 'catalogo', 'descricao', 'descricao_detalhada']]