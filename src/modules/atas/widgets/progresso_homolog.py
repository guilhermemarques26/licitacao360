from PyQt6.QtWidgets import *
from PyQt6.QtGui import *
from PyQt6.QtCore import *
from PyQt6.QtSql import QSqlQuery
import time
import pandas as pd
from pathlib import Path

from modules.utils.add_button import add_button_func, add_button_func_vermelho

# Importação inteligente: Puxa o seu Worker original e a função de DataFrame sem precisar repetir o código!
from modules.atas.widgets.worker_homologacao import Worker, save_to_dataframe


class ConclusaoDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Processamento Concluído")
        self.setup_ui()

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        message_label = QLabel("O processamento foi concluído com sucesso!")
        message_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        font = message_label.font()
        font.setPointSize(14)
        message_label.setFont(font)
        main_layout.addWidget(message_label)

        close_button = QPushButton("Fechar")
        close_button.clicked.connect(self.close)
        main_layout.addWidget(close_button)

        self.setLayout(main_layout)


class ProcessamentoWidget(QWidget):
    resultadosHomologacao = pyqtSignal(object)
    gerarPlanilhaBaseClicked = pyqtSignal()

    def __init__(self, pdf_dir, icons, model, database_ata_manager, main_window, parent=None):
        super().__init__(parent)
        self.pdf_dir = pdf_dir
        self.icon_cache = icons
        self.model = model
        self.database_ata_manager = database_ata_manager
        self.main_window = main_window
        self.homologacao_dataframe = None  
        self.setWindowTitle("Processamento")
        self.setup_ui()
        self.timer = QTimer(self)
        self.start_time = 0

    def on_pdf_dir_changed(self, new_pdf_dir):
        if hasattr(self, 'termo_homologacao_widget'):
            self.termo_homologacao_widget.pdf_dir = new_pdf_dir
            
    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        title = QLabel("Processamento de Documentos")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setFont(QFont('Arial', 16, QFont.Weight.Bold))
        main_layout.addWidget(title)

        layout_instruction = QHBoxLayout()
        layout_instruction.addStretch()
        label_pdf = QLabel("Insira os arquivos PDF na pasta")
        label_pdf.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label_pdf.setFont(QFont('Arial', 12, QFont.Weight.Bold))
        layout_instruction.addWidget(label_pdf)
            
        add_button_func("Abrir Pasta", "open-folder", self.abrir_pasta_pdf, layout_instruction, self.icon_cache, "Clique para ver instruções", button_size=(150, 30))

        label_contador = QLabel("e depois atualize o Contador")
        label_contador.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label_contador.setFont(QFont('Arial', 12, QFont.Weight.Bold))
        layout_instruction.addWidget(label_contador)  
          
        add_button_func("Atualizar", "loading-arrow", self.update_pdf_count, layout_instruction, self.icon_cache, "Clique para ver instruções",  button_size=(150, 30))
        add_button_func("Definir Pasta", "add-folder", self.definir_pasta_pdf_padrao, layout_instruction, self.icon_cache, "Clique para definir uma pasta PDF diferente", button_size=(150, 30))
        layout_instruction.addStretch()
        main_layout.addLayout(layout_instruction)

        layout_progress = QHBoxLayout()
        
        self.time_label = QLabel("Tempo decorrido: 0s")
        self.time_label.setFont(QFont('Arial', 12))
        layout_progress.addWidget(self.time_label)
                        
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setFont(QFont('Arial', 12))
        layout_progress.addWidget(self.progress_bar)

        main_layout.addLayout(layout_progress)

        self.context_area = QTextEdit()
        self.context_area.setReadOnly(True)
        self.context_area.setFont(QFont('Arial', 12))
        main_layout.addWidget(self.context_area)

        self.setup_button_layout(main_layout)
        self.setLayout(main_layout)

        self.update_pdf_count()

    def setup_button_layout(self, main_layout):
        button_layout = QHBoxLayout()
        add_button_func_vermelho("Iniciar Processamento", self.start_processing, button_layout, "Clique para iniciar", button_size=(300, 40))
        main_layout.addLayout(button_layout)

    def set_buttons_enabled(self, enabled: bool):
        for btn in self.findChildren(QPushButton):
            btn.setEnabled(enabled)

    def abrir_pasta_pdf(self):
        if not self.pdf_dir.exists():
            try:
                self.pdf_dir.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                QMessageBox.critical(self, "Erro", f"Falha ao criar o diretório PDF: {e}")
                return
        if self.pdf_dir.is_dir():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.pdf_dir)))
        else:
            QMessageBox.warning(self, "Erro", "O diretório PDF não é válido.")

    def definir_pasta_pdf_padrao(self):
        dialog = QFileDialog(self, "Selecione a pasta que contém os PDFs", str(self.pdf_dir))
        dialog.setFileMode(QFileDialog.FileMode.Directory)
        dialog.setOption(QFileDialog.Option.ShowDirsOnly, False)
        dialog.setNameFilter("Arquivos PDF (*.pdf);;Todos os Arquivos (*)")
        if dialog.exec():
            selected_folder = dialog.selectedFiles()[0]
            if selected_folder:
                self.pdf_dir = Path(selected_folder)
                if hasattr(self, 'main_window') and hasattr(self.main_window, 'pdf_dir_changed'):
                    self.main_window.pdf_dir_changed.emit(self.pdf_dir)
                self.update_pdf_count()
                QMessageBox.information(self, "Pasta Definida", f"A pasta de trabalho foi alterada para:\n{self.pdf_dir}")
            
    def update_context(self, text):
        self.context_area.append(text)

    def update_pdf_count(self):
        if self.pdf_dir.exists() and self.pdf_dir.is_dir():
            pdf_count = len(list(self.pdf_dir.glob("*.pdf")))
            self.update_context(f"Quantidade de arquivos PDF: {pdf_count}")
        else:
            self.update_context("Diretório PDF não encontrado.")

    def start_processing(self):
        self.current_dataframe = None
        if not self.verify_directories():
            return
            
        # 1. Liga o Spinner de carregamento (A interface fica bloqueada para proteção)
        if hasattr(self.main_window, 'loading_screen'):
            self.main_window.loading_screen.start("A processar relatórios de Homologação...")
            
        self.start_time = time.time()
        self.timer.timeout.connect(self.update_time)
        self.timer.start(1000)
        self.set_buttons_enabled(False)

        # 2. Inicia o seu Worker em background
        self.worker_thread = Worker(self.pdf_dir, modo="completo")
        self.worker_thread.processing_complete.connect(self.finalizar_processamento_homologacao)
        self.worker_thread.update_context_signal.connect(self.update_context)
        self.worker_thread.progress_signal.connect(self.progress_bar.setValue)

        self.worker_thread.start()

    def finalizar_processamento_homologacao(self, extracted_data):
        # 1. Desliga o Spinner de carregamento
        if hasattr(self.main_window, 'loading_screen'):
            self.main_window.loading_screen.stop()
            
        self.update_context("Processamento concluído.")
        self.timer.stop() 
        self.set_buttons_enabled(True)
        elapsed_time = int(time.time() - self.start_time)
        self.time_label.setText(f"Tempo total: {elapsed_time}s")
        
        try:
            # 2. Transforma os dados em planilha usando a função limpa importada
            self.homologacao_dataframe = save_to_dataframe(extracted_data)
            self.atualizar_ou_inserir_controle_homologacao()
            
            dialog = ConclusaoDialog(self)
            dialog.exec()
        except Exception as e:
            QMessageBox.critical(self, "Erro na Estruturação", f"Ocorreu um erro ao estruturar os dados:\n{str(e)}")

    def atualizar_ou_inserir_controle_homologacao(self): 
        if self.homologacao_dataframe is None or self.homologacao_dataframe.empty:
            print("DataFrame de homologação está vazio ou não foi criado.")
            return

        unique_combinations = self.homologacao_dataframe[['uasg', 'num_pregao', 'ano_pregao']].dropna().drop_duplicates()

        if unique_combinations.empty:
            print("Não há combinações válidas de UASG e número do pregão.")
            return

        if len(unique_combinations) > 1:
            combinations = unique_combinations.apply(lambda row: f"{row['uasg']}-{row['num_pregao']}-{row['ano_pregao']}", axis=1)
            QMessageBox.warning(None, "Combinações Múltiplas Encontradas",
                                f"As seguintes combinações únicas foram encontradas:\n" + "\n".join(combinations))
            return

        uasg, num_pregao, ano_pregao = unique_combinations.iloc[0]
        table_name = f"result_{num_pregao}_{ano_pregao}_{uasg}"

        if not self.recriar_tabela(table_name):
            return
        if not self.copiar_dados_controle_atas(table_name):
            return

        self.processar_linhas_dataframe(table_name)
        print(f"Dados do DataFrame inseridos/atualizados na tabela '{table_name}' com sucesso.")

    def recriar_tabela(self, table_name):
        delete_table_query = QSqlQuery(self.model.database())
        if not delete_table_query.exec(f"DROP TABLE IF EXISTS {table_name}"):
            print(f"Erro ao deletar a tabela '{table_name}':", delete_table_query.lastError().text())
            return False

        create_table_query = QSqlQuery(self.model.database())
        if not create_table_query.exec(f"""
            CREATE TABLE {table_name} AS
            SELECT * FROM controle_atas WHERE 1=0
        """):
            print(f"Erro ao criar a tabela '{table_name}':", create_table_query.lastError().text())
            return False
        return True

    def copiar_dados_controle_atas(self, table_name):
        copy_query = QSqlQuery(self.model.database())
        if not copy_query.exec(f"""
            INSERT INTO {table_name} (item, catalogo, descricao, descricao_detalhada)
            SELECT item, catalogo, descricao, descricao_detalhada FROM controle_atas
        """):
            print(f"Erro ao copiar colunas específicas para '{table_name}':", copy_query.lastError().text())
            return False
        return True

    def processar_linhas_dataframe(self, table_name):
        for _, row in self.homologacao_dataframe.iterrows():
            item_value = row['item']
            if self.verificar_existencia_item(table_name, item_value):
                self.atualizar_item_existente(table_name, item_value, row)
            else:
                self.inserir_novo_item(table_name, row)

    def verificar_existencia_item(self, table_name, item_value):
        check_query = QSqlQuery(self.model.database())
        check_query.prepare(f"SELECT COUNT(*) FROM {table_name} WHERE item = :item")
        check_query.bindValue(":item", item_value)
        if not check_query.exec():
            print(f"Erro ao verificar existência do item {item_value}:", check_query.lastError().text())
            return False
        check_query.next()
        return check_query.value(0) > 0

    def atualizar_item_existente(self, table_name, item_value, row):
        update_query = QSqlQuery(self.model.database())
        update_fields = ", ".join([f"{col} = :{col}" for col in self.homologacao_dataframe.columns 
                                if col not in ["item", "catalogo", "descricao", "descricao_detalhada"]])
        update_query.prepare(f"UPDATE {table_name} SET {update_fields} WHERE item = :item")

        for col in self.homologacao_dataframe.columns:
            if col not in ["catalogo", "descricao", "descricao_detalhada"]:
                update_query.bindValue(f":{col}", row[col])

        update_query.bindValue(":item", item_value)
        if not update_query.exec():
            print(f"Erro ao atualizar o item {item_value} em '{table_name}':", update_query.lastError().text())

    def inserir_novo_item(self, table_name, row):
        columns = ", ".join(self.homologacao_dataframe.columns)
        placeholders = ", ".join([f":{col}" for col in self.homologacao_dataframe.columns])
        insert_query = QSqlQuery(self.model.database())
        insert_query.prepare(f"INSERT INTO {table_name} ({columns}) VALUES ({placeholders})")

        for col in self.homologacao_dataframe.columns:
            insert_query.bindValue(f":{col}", row[col])

        if not insert_query.exec():
            print(f"Erro ao inserir o item {row['item']} em '{table_name}':", insert_query.lastError().text())

    def save_data(self, table_name):
        if isinstance(self.current_dataframe, pd.DataFrame) and not self.current_dataframe.empty:
            try:
                with self.model as conn:
                    self.current_dataframe.to_sql(table_name, conn, if_exists='replace', index=False)
            except Exception as e:
                QMessageBox.critical(self, "Erro", f"Erro ao salvar os dados no banco de dados: {e}")
        else:
            QMessageBox.critical(self, "Erro", "Nenhum DataFrame válido disponível para salvar ou o objeto não é um DataFrame.")
            
    def update_time(self):
        elapsed_time = int(time.time() - self.start_time)
        self.time_label.setText(f"Tempo decorrido: {elapsed_time}s")
        self.time_label.setFont(QFont('Arial', 12))
        
    def verify_directories(self):
        if not self.pdf_dir.exists() or not self.pdf_dir.is_dir():
            self.update_context("Diretório PDF não encontrado.")
            return False
        return True