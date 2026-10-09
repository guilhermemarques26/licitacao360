import os
import pandas as pd
import fitz
import re
import openpyxl
import gc
import json
import traceback
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
        self.input_item.setPlaceholderText("Obrigatório para encontrar as linhas (Ex: Item, Nº)")
        form_layout.addRow("Coluna do Item:", self.input_item)

        self.input_cat = QLineEdit()
        self.input_cat.setPlaceholderText("Deixe em branco para preencher manualmente")
        form_layout.addRow("Coluna do Catálogo:", self.input_cat)

        self.input_desc = QLineEdit()
        self.input_desc.setPlaceholderText("Deixe em branco para preencher manualmente")
        form_layout.addRow("Coluna da Descrição:", self.input_desc)

        self.cb_advanced_desc = QCheckBox("Preencher descrição com parâmetro avançado\n(Extrair as 3 primeiras palavras da especificação)")
        self.cb_advanced_desc.setStyleSheet("color: #1A5276; font-weight: bold; font-size: 11px;")
        self.cb_advanced_desc.setEnabled(False)
        form_layout.addRow("", self.cb_advanced_desc)

        self.input_desc_det = QLineEdit()
        self.input_desc_det.setPlaceholderText("Ex: Detalhamento, Especificação")
        form_layout.addRow("Coluna da Especificação:", self.input_desc_det)

        def atualizar_checkbox_avancado():
            if self.input_desc.text().strip() == "" and self.input_desc_det.text().strip() != "":
                self.cb_advanced_desc.setEnabled(True)
            else:
                self.cb_advanced_desc.setEnabled(False)
                self.cb_advanced_desc.setChecked(False)

        self.input_desc.textChanged.connect(atualizar_checkbox_avancado)
        self.input_desc_det.textChanged.connect(atualizar_checkbox_avancado)

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
            'col_item': self.input_item.text().strip().lower(),
            'col_cat': self.input_cat.text().strip().lower(),
            'col_desc': self.input_desc.text().strip().lower(),
            'col_desc_det': self.input_desc_det.text().strip().lower(),
            'adv_desc': self.cb_advanced_desc.isChecked() if hasattr(self, 'cb_advanced_desc') else False
        }

class WorkerExtracaoTR(QThread):
    progresso = pyqtSignal(int, int)
    concluido = pyqtSignal(object)
    erro = pyqtSignal(str)

    def __init__(self, pdf_path, config, dicionario_correcoes, parent=None):
        super().__init__(parent)
        self.pdf_path = pdf_path
        self.config = config
        self.dicionario_correcoes = dicionario_correcoes
        self.is_cancelled = False

    def cancel(self):
        self.is_cancelled = True

    def _is_header_artifact(self, text):
        if not text: return True
        t = str(text).lower()
        t = t.replace("(r$)", "").replace("r$", "").replace("%", "")
        t = re.sub(r'[^\w\s]', ' ', t) 
        
        words = [
            "de", "medida", "min", "mín", "max", "máx", "total", "unitario", "unitário", 
            "unidade", "quant", "quantidade", "valor", "situacao", "situação", 
            "item", "nº", "catmat", "catser", "codigo", "código", "descricao", "descrição", 
            "especificacao", "especificação", "objeto", "nome", "minimo", "mínimo", "maximo", "máximo",
            "un", "und", "kg", "cx", "pc", "pct", "estimado", "referencia", "referência",
            "marca", "fabricante", "modelo", "versao", "versão", "proposta", "fornecimento",
            "grupa", "grupo"
        ]
        for w in words:
            t = re.sub(r'\b' + w + r'\b', ' ', t)
            
        return len(t.strip()) == 0

    def limpar_texto_pdf(self, texto):
        if not isinstance(texto, str):
            return texto
            
        texto = re.sub(r'\(cid:\d+\)', '', texto)
        texto = re.sub(r'cid:\d+', '', texto)
        
        for erro, correcao in self.dicionario_correcoes.items():
            texto = re.sub(r'\b' + erro + r'\b', correcao, texto, flags=re.IGNORECASE)
            
        return texto.strip()

    def run(self):
        try:
            import pdfplumber
            linhas_brutas = []
            termos_rodape = [
                "manual de modelos", "consultoria-geral", "consultoria geral", 
                "da união", "secretaria de gestão", "atualização:", "atualiz", 
                "câmara nacional", "licitações e contratos", "uasg", "termo de referência",
                "informações básicas", "identidade visual", "lei nº 14.133", "lei n 14.133", 
                "de 2021", "de 2024", "nov/2024", "apêndice", "anexo"
            ]

            with pdfplumber.open(self.pdf_path) as pdf:
                total_paginas = len(pdf.pages)
                for idx, page in enumerate(pdf.pages):
                    if self.is_cancelled:
                        return

                    self.progresso.emit(idx + 1, total_paginas)
                    
                    try:
                        tables = page.extract_tables()
                        if tables:
                            for table in tables:
                                for row in table:
                                    if not row or not any(row): continue
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
                    except Exception:
                        pass

                    page.flush_cache()

            gc.collect()

            if self.is_cancelled:
                return

            lista_dados = []

            if self.config['opcao'] == 1:
                dados = {}
                current_item = None
                orphan_cat = ""
                orphan_desc = ""
                orphan_spec = ""

                for row in linhas_brutas:
                    row_clean = [self.limpar_texto_pdf(str(c).replace('\n', ' ').strip()) for c in row]
                    texto_linha = " ".join(row_clean).lower()
                    
                    is_page_break = False
                    if re.search(r'\b\d+\s+de\s+\d+\b', texto_linha) or re.search(r'página\s*\d+', texto_linha):
                        is_page_break = True
                    elif any(termo in texto_linha for termo in termos_rodape):
                        is_page_break = True
                    elif 'item' in str(row_clean[0]).lower() or ('descrição' in texto_linha and 'especificação' in texto_linha): 
                        is_page_break = True

                    if is_page_break:
                        if current_item:
                            if current_item not in dados: 
                                dados[current_item] = {"catalogo": "", "descricao": "", "descricao_detalhada": ""}
                            dados[current_item]["catalogo"] = "Preencha manualmente"
                            dados[current_item]["descricao"] = "Preencha manualmente"
                            dados[current_item]["descricao_detalhada"] = "Preencha manualmente"
                        continue

                    r_item = ""
                    primeira_celula = re.sub(r'[^\d]', '', row_clean[0])
                    if primeira_celula and row_clean[0].strip() == primeira_celula: 
                        if len(primeira_celula) <= 4 and int(primeira_celula) > 0 and int(primeira_celula) <= 5000:
                            r_item = primeira_celula
                            current_item = str(int(r_item))

                    if not r_item:
                        if current_item in dados and dados[current_item].get("descricao") == "Preencha manualmente":
                            continue
                        texto_sem_espaco = texto_linha.replace(" ", "")
                        if texto_sem_espaco.isnumeric() and len(texto_sem_espaco) <= 4:
                            continue

                    if any(termo in texto_linha for termo in termos_rodape):
                        continue 

                    if current_item in dados and dados[current_item].get("descricao") == "Preencha manualmente":
                        continue

                    r_cat = ""
                    spec_parts = []

                    for i, enumerate_cell in enumerate(row_clean):
                        if i == 0 and r_item: continue 
                        if not enumerate_cell: continue

                        limpo_cat = re.sub(r'[^\d]', '', enumerate_cell)
                        if not r_cat and len(limpo_cat) >= 5 and len(limpo_cat) <= 7 and re.fullmatch(r'\d{5,7}', limpo_cat):
                            if len(enumerate_cell) <= 12: 
                                r_cat = limpo_cat
                                continue
                        
                        if re.fullmatch(r'\d{1,4}', enumerate_cell) or re.fullmatch(r'\d{1,3}(?:\.\d{3})*(?:,\d{2})', enumerate_cell) or re.fullmatch(r'r\$\s*\d+,\d+', enumerate_cell.lower().replace('.', '')): continue
                        
                        if self._is_header_artifact(enumerate_cell):
                            continue
                            
                        spec_parts.append(enumerate_cell)

                    r_desc = ""
                    r_spec = ""
                    
                    if len(spec_parts) == 1:
                        r_spec = spec_parts[0]
                        if r_item:
                            r_desc = re.split(r'[,.;-]', r_spec)[0].strip()
                            if len(r_desc.split()) > 10:
                                r_desc = " ".join(r_desc.split()[:10])
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
                            if current_item not in dados: 
                                dados[current_item] = {"catalogo": "", "descricao": "", "descricao_detalhada": ""}

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

            elif self.config['opcao'] == 2:
                header_mapped = False
                idx_item, idx_cat, idx_desc, idx_desc_det = -1, -1, -1, -1
                
                for row in linhas_brutas:
                    row_clean = [self.limpar_texto_pdf(str(c).replace('\n', ' ').strip()) for c in row]
                    row_lower = [c.lower() for c in row_clean]
                    texto_linha = " ".join(row_clean).lower()
                    
                    is_page_break = False
                    if re.search(r'\b\d+\s+de\s+\d+\b', texto_linha) or re.search(r'página\s*\d+', texto_linha):
                        is_page_break = True
                    elif any(termo in texto_linha for termo in termos_rodape):
                        is_page_break = True
                    elif header_mapped:
                        matches_header = 0
                        for cell_val in row_lower:
                            if self.config['col_item'] and self.config['col_item'] in cell_val: matches_header += 1
                            if self.config['col_desc'] and self.config['col_desc'] in cell_val: matches_header += 1
                            if self.config['col_desc_det'] and self.config['col_desc_det'] in cell_val: matches_header += 1
                        if matches_header >= 2:
                            is_page_break = True

                    if is_page_break:
                        if lista_dados:
                            lista_dados[-1]["catalogo"] = "Preencha manualmente"
                            lista_dados[-1]["descricao"] = "Preencha manualmente"
                            lista_dados[-1]["descricao_detalhada"] = "Preencha manualmente"
                        continue
                        
                    if not header_mapped:
                        matches = 0
                        valid_configs = sum(1 for k in ['col_item', 'col_cat', 'col_desc', 'col_desc_det'] if self.config[k])
                        required_matches = min(2, valid_configs) if valid_configs > 0 else 1
                        
                        for i, cell_val in enumerate(row_lower):
                            matched_any = False
                            if self.config['col_item'] and self.config['col_item'] in cell_val: idx_item = i; matched_any = True
                            if self.config['col_cat'] and self.config['col_cat'] in cell_val: idx_cat = i; matched_any = True
                            if self.config['col_desc'] and self.config['col_desc'] in cell_val: idx_desc = i; matched_any = True
                            if self.config['col_desc_det'] and self.config['col_desc_det'] in cell_val: idx_desc_det = i; matched_any = True
                            if matched_any: matches += 1
                            
                    if not header_mapped and idx_item != -1 and matches >= required_matches:
                        header_mapped = True
                        continue
                    
                    if header_mapped:
                        if not any(row_clean): continue
                        
                        v_item = row_clean[idx_item] if idx_item != -1 and idx_item < len(row_clean) else ""
                        v_cat = row_clean[idx_cat] if idx_cat != -1 and idx_cat < len(row_clean) else ""
                        v_desc = row_clean[idx_desc] if idx_desc != -1 and idx_desc < len(row_clean) else ""
                        v_desc_det = row_clean[idx_desc_det] if idx_desc_det != -1 and idx_desc_det < len(row_clean) else ""
                        
                        v_item_limpo = ""
                        num_str = re.sub(r'[^\d]', '', v_item)
                        if num_str and v_item.strip() == num_str:
                            if len(num_str) <= 4 and int(num_str) > 0 and int(num_str) <= 5000:
                                v_item_limpo = num_str
                        
                        if not v_item_limpo:
                            if lista_dados and lista_dados[-1]["descricao_detalhada"] == "Preencha manualmente" and lista_dados[-1]["catalogo"] == "Preencha manualmente":
                                continue

                            texto_sem_espaco = texto_linha.replace(" ", "")
                            if texto_sem_espaco.isnumeric() and len(texto_sem_espaco) <= 4:
                                continue

                        if self._is_header_artifact(v_desc): v_desc = ""
                        if self._is_header_artifact(v_desc_det): v_desc_det = ""

                        if v_item_limpo: 
                            lista_dados.append({
                                "item": v_item_limpo,
                                "catalogo": v_cat if self.config['col_cat'] else "Preencha manualmente",
                                "descricao": v_desc if self.config['col_desc'] else "Preencha manualmente",
                                "descricao_detalhada": v_desc_det if self.config['col_desc_det'] else "Preencha manualmente"
                            })
                        else:
                            if lista_dados:
                                if self.config['col_cat'] and v_cat and not self._is_header_artifact(v_cat): 
                                    if lista_dados[-1]["catalogo"] == "Preencha manualmente":
                                        lista_dados[-1]["catalogo"] = v_cat
                                    else:
                                        lista_dados[-1]["catalogo"] += " " + v_cat
                                        
                                if self.config['col_desc'] and v_desc: 
                                    if lista_dados[-1]["descricao"] == "Preencha manualmente":
                                        lista_dados[-1]["descricao"] = v_desc
                                    else:
                                        lista_dados[-1]["descricao"] += " " + v_desc
                                        
                                if self.config['col_desc_det'] and v_desc_det: 
                                    if lista_dados[-1]["descricao_detalhada"] == "Preencha manualmente":
                                        lista_dados[-1]["descricao_detalhada"] = v_desc_det
                                    else:
                                        lista_dados[-1]["descricao_detalhada"] += " " + v_desc_det

                if self.config['adv_desc']:
                    for dado in lista_dados:
                        if dado['descricao_detalhada'] and dado['descricao_detalhada'] != "Preencha manualmente":
                            palavras = dado['descricao_detalhada'].split()
                            dado['descricao'] = " ".join(palavras[:3])

            df = pd.DataFrame(lista_dados)
            if df.empty:
                self.concluido.emit(df)
                return

            def blindagem_catalogo(valor):
                if pd.isna(valor) or str(valor).strip() == "" or valor == "Preencha manualmente":
                    return "Preencha manualmente"
                valor_str = str(valor)
                sequencias = re.findall(r'(?<![\d.,])\d{5,7}(?![\d.,])', valor_str)
                if sequencias: return sequencias[0]
                numeros = re.sub(r'[^\d]', '', valor_str)
                if 5 <= len(numeros) <= 7 and "." not in valor_str and "," not in valor_str:
                    return numeros
                return "Preencha manualmente"

            df['catalogo'] = df['catalogo'].apply(blindagem_catalogo)
            df['temp_item'] = pd.to_numeric(df['item'], errors='coerce')
            df = df[(df['temp_item'].notna()) & (df['temp_item'] > 0) & (df['temp_item'] <= 5000)].copy()
            
            for col in ['item', 'catalogo', 'descricao', 'descricao_detalhada']:
                if col not in df.columns: df[col] = ""

            for col in ['catalogo', 'descricao', 'descricao_detalhada']:
                df[col] = df[col].apply(lambda x: 'Preencha manualmente' if pd.isna(x) or str(x).strip() == '' else x)

            if not df.empty:
                maior_item = int(df['temp_item'].max())
                itens_encontrados = set(df['temp_item'].astype(int).tolist())
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
            self.concluido.emit(df[['item', 'catalogo', 'descricao', 'descricao_detalhada']])

        except Exception as e:
            self.erro.emit(traceback.format_exc())

# ==============================================================================
# CORREÇÃO: A CLASSE ABAIXO FOI MOVIDA PARA FORA DO WORKER (INDENTAÇÃO CORRIGIDA)
# ==============================================================================
class TermoReferenciaWidget(QWidget): 
    abrirTabelaNova = pyqtSignal()
    carregarTabela = pyqtSignal()  
    configurarSqlModelSignal = pyqtSignal() 
    extrairTrSignal = pyqtSignal() 
    limparTabelaSignal = pyqtSignal() 

    def __init__(self, parent, icons):
        super().__init__(parent)
        self.setWindowTitle("Termo de Referência")
        self.resize(800, 600)
        self.parent = parent
        self.icons = icons
        self.worker_thread = None
        
        self.layout = QVBoxLayout(self)
        
        title = QLabel("Especificação do Termo de Referência")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setFont(QFont('Arial', 16, QFont.Weight.Bold))
        self.layout.addWidget(title)

        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        add_button("Tabela em Branco", "excel_down", self.abrirTabelaNova, button_layout, self.icons, tooltip="Cria uma tabela vazia", button_size=(150, 30))
        add_button("Extrair TR", "pdf", self.extrairTrSignal, button_layout, self.icons, tooltip="Extrai as especificações do PDF", button_size=(150, 30))
        
        self.extrairTrSignal.connect(self.abrir_dialog_config_extracao)
        
        add_button("Carregar Tabela", "excel_up", self.carregarTabela, button_layout, self.icons, tooltip="Carrega a tabela preenchida para o banco", button_size=(150, 30))
        add_button("Limpar Tabela", "delete", self.limparTabelaSignal, button_layout, self.icons, tooltip="Apaga todos os dados da tabela atual", button_size=(150, 30))
        
        button_layout.addStretch()
        self.layout.addLayout(button_layout)
        
        info_layout = QHBoxLayout()
        guia_label = QLabel(
            "<b>Guia Rápido:</b><br>"
            "1. <b>Extrair TR:</b> Gere a planilha inicial a partir do PDF.<br>"
            "2. <b>Preencher Manualmente:</b> Abra o Excel gerado e corrija os itens a <font color='red'>vermelho</font>.<br>"
            "3. <b>Carregar Tabela:</b> Guarde o Excel e importe-o de volta para o sistema."
        )
        guia_label.setTextFormat(Qt.TextFormat.RichText)
        guia_label.setStyleSheet("background-color: #EBF5FB; color: #2C3E50; padding: 10px; border-radius: 5px; border: 1px solid #AED6F1; font-size: 13px;")
        info_layout.addWidget(guia_label)
        info_layout.addStretch() 
        
        self.btn_dic = QPushButton("⚙️ Configurar dicionário de OCR")
        self.btn_dic.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_dic.setToolTip("Abra o bloco de notas para ensinar o programa a corrigir palavras do PDF.")
        self.btn_dic.setStyleSheet("""
            QPushButton { 
                color: #85929E; 
                font-size: 11px; 
                background: transparent; 
                border: none; 
                text-decoration: underline;
                padding-top: 20px;
            } 
            QPushButton:hover { 
                color: #2E86C1; 
            }
        """)
        self.btn_dic.clicked.connect(self.abrir_arquivo_dicionario)
        info_layout.addWidget(self.btn_dic, alignment=Qt.AlignmentFlag.AlignTop)
        self.layout.addLayout(info_layout)

        self.table_view = QTableView(self)
        self.table_view.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)  
        self.table_view.verticalHeader().setVisible(False)  
        
        self.delegado_alerta = AlertaFaltaDelegate(self)
        self.table_view.setItemDelegate(self.delegado_alerta)
        self.layout.addWidget(self.table_view)

        self.table_view.setStyleSheet("""
            QTableView { background-color: #F3F3F3; color: #333333; gridline-color: #CCCCCC; font-size: 14px; margin-top: 10px;}
            QTableView::item:selected { background-color: #E0E0E0; color: #000000; }
            QTableView::item { border: 1px solid transparent; padding: 5px; }
            QHeaderView::section { background-color: #D6D6D6; color: #333333; font-weight: bold; font-size: 14px; padding: 4px; border: 1px solid #CCCCCC; }
        """)

        self.dicionario_correcoes = self.carregar_dicionario()
        self.configurarSqlModelSignal.emit()

    def carregar_dicionario(self):
        dir_app = Path.home() / "Licitacao360"
        dir_app.mkdir(exist_ok=True)
        caminho_dic = dir_app / "dicionario_correcoes.json"
        
        dic_padrao = {
            "fomo": "forno", "inax": "inox", "inar": "inox", "moxidável": "inoxidável",
            "dietrica": "elétrica", "ples": "pães", "queintadores": "queimadores",
            "impesz": "limpeza", "removiven": "removíveis", "gastronomicies": "gastronômicas",
            "cacção": "cocção", "kain": "com", "nülen": "núcleo", "Masseita": "Masseira",
            "des nado": "destinado", "desnado": "destinado",
            "des nada": "destinada", "desnada": "destinada",
            "quan dade": "quantidade", "quandade": "quantidade",
            "quan dades": "quantidades", "quandades": "quantidades",
            "iden ficação": "identificação", "idenficação": "identificação",
            "especi ficação": "especificação", "especicação": "especificação",
            "garan ndo": "garantindo", "garanndo": "garantindo",
            "compa vel": "compatível", "compavel": "compatível",
            "caracterís cas": "características", "caracteríscas": "características",
            "plás co": "plástico", "plásco": "plástico",
            "plás cos": "plásticos", "pláscos": "plásticos",
            "automá ca": "automática", "automáca": "automática",
            "automá co": "automático", "automáco": "automático",
            "resis ncia": "resistência", "resisncia": "resistência",
            "resis nte": "resistente", "resisnte": "resistente",
            "resis ntes": "resistentes", "resisntes": "resistentes",
            "sen do": "sentido", 
            "polie leno": "polietileno", "polieleno": "polietileno",
            "subme do": "submetido", "submedo": "submetido",
            "reves mento": "revestimento", "revesmento": "revestimento",
            "con nua": "contínua", "connua": "contínua",
            "con nuo": "contínuo", "connuo": "contínuo",
            "idên cos": "idênticos", "idêncos": "idênticos",
            "sani rio": "sanitário", "sanirio": "sanitário",
            "refei rio": "refeitório", "refeirio": "refeitório",
            "of cial": "oficial", "ofcial": "oficial",
            "fí sico": "físico", "físico": "físico",
            "elétri ca": "elétrica", "eletrica": "elétrica",
            "ulizados": "utilizados", "faadora": "fatiadora",
            "faamento": "fatiamento", "faar": "fatiar",
            "mulfuncional": "multifuncional", "Mulprocessador": "Multiprocessador",
            "vercal": "vertical", " Equetagem": " Etiquetagem",
            "administravos": "administrativos", "garana": "garantia",
            "produvidade": "produtividade", "venladores": "ventiladores",
            "anaderente": "antiaderente", "anaderentes": "antiaderentes",
            "arculada": "articulada", "angotejamento": "antigotejamento",
            "Domésca": "Doméstica", "ancorrosiva": "anticorrosiva",
            "energéca": "energética", "Autodiagnósco": "Autodiagnóstico",
            "herméco": "hermético", "disposivos": "dispositivos",
            " ras ": " tiras ", "serpenna": "serpentina", " po ": " tipo "
        }
        
        if not caminho_dic.exists():
            try:
                with open(caminho_dic, 'w', encoding='utf-8') as f:
                    json.dump(dic_padrao, f, indent=4, ensure_ascii=False)
            except Exception: pass
            return dic_padrao
        else:
            try:
                with open(caminho_dic, 'r', encoding='utf-8') as f:
                    dic_usuario = json.load(f)
                    dic_atualizado = dic_padrao.copy()
                    dic_atualizado.update(dic_usuario)
                    with open(caminho_dic, 'w', encoding='utf-8') as f_out:
                        json.dump(dic_atualizado, f_out, indent=4, ensure_ascii=False)
                    return dic_atualizado
            except Exception:
                return dic_padrao

    def abrir_arquivo_dicionario(self):
        dir_app = Path.home() / "Licitacao360"
        caminho_dic = dir_app / "dicionario_correcoes.json"
        if not caminho_dic.exists():
            self.carregar_dicionario()
        try:
            os.startfile(str(caminho_dic))
        except Exception:
            QMessageBox.warning(self, "Erro", f"Não foi possível abrir o arquivo automaticamente.\nPasta: {dir_app}")

    def abrir_dialog_config_extracao(self):
        try:
            dialog = ConfigExtracaoDialog(self)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                config = dialog.get_config()
                self.dicionario_correcoes = self.carregar_dicionario()
                QApplication.processEvents()
                self.extrairPdfParaExcel(config)
        except Exception as e:
            QMessageBox.critical(self, "Erro na Inicialização", f"Ocorreu um erro ao abrir a configuração:\n{traceback.format_exc()}")

    def extrairPdfParaExcel(self, config):
        try:
            dir_seguro = os.path.expanduser("~")
            
            dialog_abrir = QFileDialog(self, "Selecione o PDF do Termo de Referência")
            dialog_abrir.setDirectory(dir_seguro)
            dialog_abrir.setNameFilter("Arquivos PDF (*.pdf)")
            dialog_abrir.setFileMode(QFileDialog.FileMode.ExistingFile)

            if dialog_abrir.exec() != QDialog.DialogCode.Accepted:
                return

            arquivos_selecionados = dialog_abrir.selectedFiles()
            if not arquivos_selecionados:
                return
            pdf_path = arquivos_selecionados[0]

            QApplication.processEvents()

            dialog_salvar = QFileDialog(self, "Onde deseja salvar a Planilha Preenchida?")
            dialog_salvar.setDirectory(dir_seguro)
            dialog_salvar.setNameFilter("Planilha Excel (*.xlsx)")
            dialog_salvar.selectFile("TR_Extraido.xlsx")
            dialog_salvar.setAcceptMode(QFileDialog.AcceptMode.AcceptSave)
            dialog_salvar.setFileMode(QFileDialog.FileMode.AnyFile)

            if dialog_salvar.exec() != QDialog.DialogCode.Accepted:
                return

            arquivos_salvar = dialog_salvar.selectedFiles()
            if not arquivos_salvar:
                return
            save_path = arquivos_salvar[0]
            if not save_path.lower().endswith(".xlsx"):
                save_path += ".xlsx"

            loading = QProgressDialog("Iniciando extração do PDF...", "Cancelar", 0, 100, self)
            loading.setWindowTitle("Processando Termo de Referência")
            loading.setWindowModality(Qt.WindowModality.WindowModal)
            loading.setMinimumDuration(0)
            loading.setValue(0)
            loading.show()

            self.worker_thread = WorkerExtracaoTR(pdf_path, config, self.dicionario_correcoes)
            
            def atualizar_progresso(atual, total):
                if total > 0:
                    porcentagem = int((atual / total) * 100)
                    loading.setValue(porcentagem)
                    loading.setLabelText(f"Processando página {atual} de {total}... ({porcentagem}%)")

            def finalizar_extracao(df):
                loading.close()
                if df.empty:
                    QMessageBox.warning(self, "Aviso", "Não foi possível extrair os itens deste PDF com a configuração selecionada.\nTente usar a Opção 2 e mapear os cabeçalhos manualmente.")
                    return

                try:
                    df.to_excel(save_path, index=False)
                    wb = openpyxl.load_workbook(save_path)
                    ws = wb.active
                    fonte_vermelha = Font(color="FF0000", bold=True)
                    for row in ws.iter_rows():
                        for cell in row:
                            if cell.value == "Preencha manualmente":
                                cell.font = fonte_vermelha
                    wb.save(save_path)

                    QMessageBox.information(
                        self, "Sucesso", 
                        f"Planilha gerada com sucesso em:\n{save_path}\n\n"
                        "1. Abra o arquivo Excel.\n"
                        "2. Corrija as linhas em vermelho.\n"
                        "3. Salve o arquivo e clique em 'Carregar Tabela'."
                    )
                except Exception as e:
                    QMessageBox.critical(self, "Erro ao Salvar", f"Não foi possível salvar o arquivo Excel:\n{e}")

            def tratar_erro(msg):
                loading.close()
                QMessageBox.critical(self, "Erro Crítico", f"Ocorreu um erro durante a extração:\n{msg}")

            self.worker_thread.progresso.connect(atualizar_progresso)
            self.worker_thread.concluido.connect(finalizar_extracao)
            self.worker_thread.erro.connect(tratar_erro)
            loading.canceled.connect(self.worker_thread.cancel)

            self.worker_thread.start()

        except Exception as e:
            QMessageBox.critical(self, "Erro Inesperado", f"Falha ao executar a extração:\n{traceback.format_exc()}")