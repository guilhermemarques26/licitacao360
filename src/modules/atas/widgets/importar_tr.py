import os
import pandas as pd
import fitz
import re
import openpyxl
import gc
import json
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
        
        self.layout = QVBoxLayout(self)
        
        # 1. TÍTULO PRINCIPAL
        title = QLabel("Especificação do Termo de Referência")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setFont(QFont('Arial', 16, QFont.Weight.Bold))
        self.layout.addWidget(title)

        # 2. BOTÕES DE AÇÃO
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        add_button("Tabela em Branco", "excel_down", self.abrirTabelaNova, button_layout, self.icons, tooltip="Cria uma tabela vazia", button_size=(180, 30))
        add_button("Extrair TR", "pdf", self.extrairTrSignal, button_layout, self.icons, tooltip="Extrai as especificações do PDF", button_size=(180, 30))
        
        self.extrairTrSignal.connect(self.abrir_dialog_config_extracao)
        
        add_button("Carregar Tabela", "excel_up", self.carregarTabela, button_layout, self.icons, tooltip="Carrega a tabela preenchida para o banco", button_size=(180, 30))
        add_button("Limpar Tabela", "delete", self.limparTabelaSignal, button_layout, self.icons, tooltip="Apaga todos os dados da tabela atual", button_size=(180, 30))
        
        button_layout.addStretch()
        self.layout.addLayout(button_layout)
        
        # 3. GUIA PASSO A PASSO E BOTÃO DE DICIONÁRIO (UI Otimizada)
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

        # 4. TABELA
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
            except Exception:
                pass
            return dic_padrao
        else:
            try:
                with open(caminho_dic, 'r', encoding='utf-8') as f:
                    dic_usuario = json.load(f)
                    
                    dic_atualizado = dic_padrao.copy()
                    dic_atualizado.update(dic_usuario)
                    
                    with open(caminho_dic, 'w', encoding='utf-8') as f:
                        json.dump(dic_atualizado, f, indent=4, ensure_ascii=False)
                        
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
        except Exception as e:
            QMessageBox.warning(self, "Erro", f"Não foi possível abrir o arquivo automaticamente.\nEle está salvo na pasta: {dir_app}")

    def abrir_dialog_config_extracao(self):
        dialog = ConfigExtracaoDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            config = dialog.get_config()
            self.dicionario_correcoes = self.carregar_dicionario()
            self.extrairPdfParaExcel(config)

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

    def extrairPdfParaExcel(self, config):
        dir_seguro = os.path.expanduser("~")
        pdf_path, _ = QFileDialog.getOpenFileName