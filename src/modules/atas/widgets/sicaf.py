from PyQt6.QtWidgets import *
from PyQt6.QtGui import *
from PyQt6.QtCore import *
from PyQt6.QtSql import QSqlQuery
import re
import time
import pandas as pd
from pathlib import Path
from modules.atas.widgets.worker_homologacao import TreeViewWindow, WorkerSICAF
import logging
from modules.utils.add_button import add_button_func_vermelho, add_button_copy, add_button_func
from modules.utils.linha_layout import linha_divisoria_layout

class RegistroSICAFDialog(QWidget):
    def __init__(self, pdf_dir, model, icons, database_ata_manager, main_window, parent=None):
        super().__init__(parent)
        self.sicaf_dir = pdf_dir / 'pasta_sicaf'
        self.model = model
        self.icons = icons
        self.database_ata_manager = database_ata_manager
        self.main_window = main_window
        self.homologacao_dataframe = None        
        self.setWindowTitle("Registro SICAF")
        self.setup_ui()

    def setup_ui(self):
        main_layout = QVBoxLayout(self)

        if self.homologacao_dataframe is None:
            self.homologacao_dataframe = pd.DataFrame()

        title = QLabel("Processamento de Documentos")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setFont(QFont('Arial', 16, QFont.Weight.Bold))
        main_layout.addWidget(title)

        selecao_layout = QHBoxLayout()

        spacer = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        selecao_layout.addItem(spacer)

        selecao_label = QLabel("Selecione a Licitação:")
        selecao_label.setFont(QFont('Arial', 14))
        selecao_layout.addWidget(selecao_label)

        self.selecao_combobox = QComboBox()
        self.selecao_combobox.setFixedWidth(360)
        self.selecao_combobox.setFont(QFont('Arial', 12))
        selecao_layout.addWidget(self.selecao_combobox)

        selecao_layout.addStretch()
        main_layout.addLayout(selecao_layout)

        self.carregar_tabelas_result()

        linha_divisoria1, spacer_baixo_linha1 = linha_divisoria_layout()
        main_layout.addWidget(linha_divisoria1)
        main_layout.addSpacerItem(spacer_baixo_linha1)   

        layout_conteudo = QHBoxLayout()

        left_layout = self.criar_layout_esquerdo()
        layout_conteudo.addLayout(left_layout)

        right_widget = self.criar_layout_direito()
        layout_conteudo.addWidget(right_widget)

        main_layout.addLayout(layout_conteudo)

        linha_divisoria2, spacer_baixo_linha2 = linha_divisoria_layout()
        main_layout.addWidget(linha_divisoria2)
        main_layout.addSpacerItem(spacer_baixo_linha2)   

        button_layout = QHBoxLayout()
        button_layout.addStretch()
        add_button_func_vermelho("Iniciar Processamento", self.iniciar_processamento_sicaf, button_layout, "Iniciar processamento do SICAF", button_size=(300, 40))
        button_layout.addStretch()
        main_layout.addLayout(button_layout)

        self.atualizar_lista()

    def open_results_treeview(self):
        if self.homologacao_dataframe is not None and not self.homologacao_dataframe.empty:
            tree_view_window = TreeViewWindow(
                dataframe=self.homologacao_dataframe,
                icons_dir=self.icons,
                database_ata_manager=self.database_ata_manager,
                parent=self
            )
            tree_view_window.exec()
        else:
            QMessageBox.warning(self, "Erro", "Não há dados disponíveis para mostrar no TreeView.")

    def carregar_tabelas_result(self):
        tabelas_result = self.database_ata_manager.get_tables_with_keyword("result")
        self.selecao_combobox.clear()
        self.selecao_combobox.addItem("Selecione a Tabela")
        self.selecao_combobox.setCurrentIndex(0)

        for tabela in tabelas_result:
            if tabela.startswith("result"):
                self.selecao_combobox.addItem(tabela)

        self.selecao_combobox.currentIndexChanged.connect(self.atualizar_dataframe_selecionado)

    def atualizar_dataframe_selecionado(self):
        tabela = self.selecao_combobox.currentText()
        if tabela == "Selecione a Tabela":
            return

        if tabela:
            self.homologacao_dataframe = self.database_ata_manager.load_table_to_dataframe(tabela)
            if 'situacao' not in self.homologacao_dataframe.columns:
                self.homologacao_dataframe['situacao'] = None

            self.atualizar_lista()
        else:
            self.homologacao_dataframe = pd.DataFrame()

    def criar_layout_esquerdo(self):
        left_layout = QVBoxLayout()
        legenda_layout = self.criar_legenda_layout()
        left_layout.addLayout(legenda_layout)

        linha_divisoria2, spacer_baixo_linha2 = linha_divisoria_layout()
        left_layout.addWidget(linha_divisoria2)
        left_layout.addSpacerItem(spacer_baixo_linha2)   

        self.left_list_widget = QListWidget()
        self.left_list_widget.setStyleSheet("QListWidget::item { text-align: left; }")
        left_layout.addWidget(self.left_list_widget)

        return left_layout

    def iniciar_processamento_sicaf(self):
        if not self.sicaf_dir.exists():
            QMessageBox.warning(self, "Erro", "A pasta SICAF não existe.")
            return        

        self.worker = WorkerSICAF(self.sicaf_dir)
        self.worker.processing_complete.connect(self.on_processing_complete)
        self.worker.start()
        self.atualizar_lista()
        
    def on_processing_complete(self, dataframes):
        """Salva os dados extraídos no banco de dados 'registro_sicaf'."""
        for df in dataframes:
            for _, row in df.iterrows():
                empresa = row.get('empresa')
                cnpj = row.get('cnpj')
                nome_fantasia = row.get('nome_fantasia')
                endereco = row.get('endereco')
                cep = row.get('cep')
                municipio = row.get('municipio')
                uf = row.get('uf')  # CAPTURANDO A UF
                telefone = row.get('telefone')
                email = row.get('email')
                responsavel_legal = row.get('nome')

                check_query = "SELECT 1 FROM registro_sicaf WHERE cnpj = ?"
                exists = self.database_ata_manager.execute_query(check_query, (cnpj,))

                if exists:
                    update_query = """
                    UPDATE registro_sicaf SET 
                        empresa = ?, 
                        nome_fantasia = ?, 
                        endereco = ?, 
                        cep = ?, 
                        municipio = ?, 
                        uf = ?, 
                        telefone = ?, 
                        email = ?, 
                        responsavel_legal = ?
                    WHERE cnpj = ?
                    """
                    params = (empresa, nome_fantasia, endereco, cep, municipio, uf, telefone, email, responsavel_legal, cnpj)
                    try:
                        self.database_ata_manager.execute_update(update_query, params)
                    except Exception as e:
                        logging.error(f"Erro ao atualizar registro de {empresa}: {e}")
                else:
                    insert_query = """
                    INSERT INTO registro_sicaf (empresa, cnpj, nome_fantasia, endereco, cep, municipio, uf, telefone, email, responsavel_legal)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """
                    params = (empresa, cnpj, nome_fantasia, endereco, cep, municipio, uf, telefone, email, responsavel_legal)
                    try:
                        self.database_ata_manager.execute_query(insert_query, params)
                    except Exception as e:
                        logging.error(f"Erro ao inserir registro de {empresa}: {e}")
        
        QMessageBox.information(self, "Processamento Completo", "Todos os registros foram processados e salvos no banco de dados com sucesso.")
        self.atualizar_lista()

    def criar_legenda_layout(self):
        legenda_layout = QVBoxLayout()
        legenda_hlayout = QHBoxLayout()
        legenda_hlayout.setAlignment(Qt.AlignmentFlag.AlignLeft)

        legenda_text = QLabel("Legenda: ")
        confirm_icon = QLabel()
        confirm_icon.setPixmap(self.icons["check"].pixmap(16, 16))
        confirm_text = QLabel("SICAF encontrado")

        cancel_icon = QLabel()
        cancel_icon.setPixmap(self.icons["cancel"].pixmap(16, 16))
        cancel_text = QLabel("SICAF não encontrado")

        legenda_hlayout.addWidget(legenda_text)
        legenda_hlayout.addWidget(confirm_icon)
        legenda_hlayout.addWidget(confirm_text)
        legenda_hlayout.addWidget(cancel_icon)
        legenda_hlayout.addWidget(cancel_text)
        legenda_layout.addLayout(legenda_hlayout)

        copy_hlayout = QHBoxLayout()
        copy_hlayout.setAlignment(Qt.AlignmentFlag.AlignLeft)

        copiar_text = QLabel("Clique no botão")
        copy_icon = QLabel()
        copy_icon.setPixmap(self.icons["copy"].pixmap(22, 22))
        copiar_text2 = QLabel("para copiar o CNPJ para área de transferência e facilitar a busca do SICAF.")    

        copy_hlayout.addWidget(copiar_text)
        copy_hlayout.addWidget(copy_icon)
        copy_hlayout.addWidget(copiar_text2)
        legenda_layout.addLayout(copy_hlayout)
        
        credenciais_text = QLabel("Consulte apenas o 'Nível 1 - Credenciamento' do SICAF e insira o PDF na pasta de processamento")
        legenda_layout.addWidget(credenciais_text)
        return legenda_layout

    def criar_layout_direito(self):
        right_widget = QWidget()
        right_widget.setFixedWidth(350)
        right_layout = QVBoxLayout(right_widget)
        right_layout.setSpacing(1)
        right_layout.setContentsMargins(0, 2, 0, 2)            
        right_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)

        top_right_layout = self.criar_botoes_direitos()
        right_layout.addLayout(top_right_layout)
        right_layout.setSpacing(5)

        self.pdf_list_widget = QListWidget()
        self.load_pdf_files()
        right_layout.addWidget(self.pdf_list_widget)

        layout_contador_pdf = QHBoxLayout()
        layout_contador_pdf.addStretch()        
        self.right_label = QLabel(self.obter_texto_arquivos_pdf())
        self.right_label.setFont(QFont('Arial', 12, QFont.Weight.Bold))     
        layout_contador_pdf.addWidget(self.right_label)
        layout_contador_pdf.addStretch()
        right_layout.addLayout(layout_contador_pdf)

        return right_widget

    def load_pdf_files(self):
        if self.sicaf_dir.exists() and self.sicaf_dir.is_dir():
            pdf_files = list(self.sicaf_dir.glob("*.pdf"))
            for pdf_file in pdf_files:
                self.pdf_list_widget.addItem(pdf_file.name)
        else:
            self.pdf_list_widget.addItem("Nenhum arquivo PDF encontrado.")

    def criar_botoes_direitos(self):
        top_right_layout = QHBoxLayout()
        add_button_func("Abrir Pasta", "open-folder", self.abrir_pasta_sicaf, top_right_layout, self.icons, "Clique para abrir a pasta de processamento do SICAF",  button_size=(150, 30))
        add_button_func("Atualizar", "loading-arrow", self.atualizar_lista, top_right_layout, self.icons, "Clique para atualizar os arquivos PDF",  button_size=(150, 30))
        return top_right_layout

    def obter_texto_arquivos_pdf(self):
        quantidade = self.count_pdf_files()
        if quantidade == 0:
            return "Nenhum arquivo PDF encontrado na pasta."
        elif quantidade == 1:
            return "1 arquivo PDF encontrado na pasta."
        else:
            return f"{quantidade} arquivos PDF encontrados na pasta."
        
    def count_pdf_files(self):
        if self.sicaf_dir.exists() and self.sicaf_dir.is_dir():
            return len(list(self.sicaf_dir.glob("*.pdf")))
        return 0
            
    def atualizar_lista(self):
        create_table_query = """
        CREATE TABLE IF NOT EXISTS registro_sicaf (
            empresa TEXT,
            cnpj TEXT PRIMARY KEY,
            nome_fantasia TEXT,
            endereco TEXT,
            cep TEXT,
            municipio TEXT,
            uf TEXT,
            telefone TEXT,
            email TEXT,
            responsavel_legal TEXT
        )
        """
        try:
            self.database_ata_manager.execute_query(create_table_query)
            try:
                self.database_ata_manager.execute_query("ALTER TABLE registro_sicaf ADD COLUMN uf TEXT")
            except Exception:
                pass
        except Exception as e:
            QMessageBox.critical(self, "Erro no Banco de Dados", f"Erro ao criar a tabela registro_sicaf: {e}")
            return

        if self.homologacao_dataframe is None or self.homologacao_dataframe.empty:
            self.homologacao_dataframe = pd.DataFrame(columns=["empresa", "cnpj"])
        else:
            for col in ["empresa", "cnpj"]:
                if col not in self.homologacao_dataframe.columns:
                    self.homologacao_dataframe[col] = None

        self.left_list_widget.clear()
        unique_combinations = self.homologacao_dataframe[["empresa", "cnpj"]].drop_duplicates()

        for _, row in unique_combinations.iterrows():
            empresa = row["empresa"]
            cnpj = row["cnpj"]
            
            if pd.isnull(empresa) or pd.isnull(cnpj):
                continue

            check_cnpj_query = "SELECT 1 FROM registro_sicaf WHERE cnpj = ?"
            exists = self.database_ata_manager.execute_query(check_cnpj_query, (cnpj,))

            if not exists:
                insert_query = "INSERT INTO registro_sicaf (empresa, cnpj) VALUES (?, ?)"
                try:
                    self.database_ata_manager.execute_query(insert_query, (empresa, cnpj))
                except Exception as e:
                    logging.error(f"Erro ao inserir empresa e CNPJ: {e}")

            item_widget = QWidget()
            item_layout = QHBoxLayout(item_widget)
            item_layout.setSpacing(1)
            item_layout.setContentsMargins(0, 2, 0, 2)            
            item_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)

            icon_label = QLabel()
            icon_label.setPixmap(self.get_icon_for_cnpj(cnpj).pixmap(16, 16))

            empresa_label = QLabel(f"{cnpj} - {empresa}")
            copiar_button = add_button_copy(
                text="",
                icon_name="copy",
                slot=lambda _, cnpj=cnpj: self.copiar_para_area_de_transferencia(cnpj),
                layout=item_layout,
                icons=self.icons,
                tooltip="Copiar para área de transferência"
            )

            item_layout.addWidget(icon_label)
            item_layout.addWidget(empresa_label)
            
            list_item = QListWidgetItem(self.left_list_widget)
            list_item.setSizeHint(item_widget.sizeHint())
            self.left_list_widget.addItem(list_item)
            self.left_list_widget.setItemWidget(list_item, item_widget)

        self.pdf_list_widget.clear()
        pdf_files = list(self.sicaf_dir.glob("*.pdf"))

        if pdf_files:
            for pdf_file in pdf_files:
                self.pdf_list_widget.addItem(pdf_file.name)
        else:
            self.pdf_list_widget.addItem("Nenhum arquivo PDF encontrado.")

        self.right_label.setText(self.obter_texto_arquivos_pdf())

    def abrir_pasta_sicaf(self):
        if not self.sicaf_dir.exists():
            self.sicaf_dir.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.sicaf_dir)))

    def get_icon_for_cnpj(self, cnpj):
        try:
            query = "SELECT endereco FROM registro_sicaf WHERE cnpj = ?"
            result = self.database_ata_manager.execute_query(query, (cnpj,))
            if result:
                endereco = result[0][0]
                if endereco and endereco.strip():
                    return self.icons["check"]
            return self.icons["cancel"]
        except Exception:
            return self.icons["cancel"]

    def copiar_para_area_de_transferencia(self, cnpj):
        clipboard = QApplication.clipboard()
        clipboard.setText(cnpj)

        confirmation_label = QLabel(f"O CNPJ {cnpj} foi copiado para a área de transferência.", self)
        confirmation_label.setStyleSheet("""
            QLabel {
                background-color: #009B3A;
                color: white;
                font-size: 16px;
                border-radius: 5px;
                padding: 10px;
            }
        """)
        confirmation_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        confirmation_label.setFixedSize(550, 50)
        confirmation_label.move(
            self.width() // 2 - confirmation_label.width() // 2,
            self.height() // 2 - confirmation_label.height() // 2
        )
        confirmation_label.show()
        QTimer.singleShot(700, confirmation_label.close)