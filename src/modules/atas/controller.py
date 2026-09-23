from PyQt6.QtCore import *
from PyQt6.QtWidgets import QProgressDialog, QMessageBox
from pathlib import Path
import pandas as pd
from modules.atas.widgets.worker_homologacao import Worker 
# Importa a função de processamento da Homologação (NÃO APAGUE O ARQUIVO progresso_homolog.py)
from modules.atas.widgets.progresso_homolog import save_to_dataframe

class GerarAtasController(QObject): 
    def __init__(self, icons, view, model):
        super().__init__()
        self.icons = icons
        self.view = view
        self.model = model.setup_model("controle_atas")
        self.worker = None
        self.df_tr_temp = pd.DataFrame()
        self.setup_connections()

    def setup_connections(self):
        self.view.instructionSignal.connect(self.instrucoes)
        self.view.trSignal.connect(self.termo_referencia)
        self.view.sicafSignal.connect(self.sicaf_widget)
        self.view.atasSignal.connect(self.gerar_atas)

        self.view.tr_widget.configurarSqlModelSignal.connect(self.configurar_sql_model)
        self.view.tr_widget.limparTabelaSignal.connect(self.limpar_tabela) 
        
        # Conexão da Extração Dupla
        self.view.tr_widget.iniciarExtracaoDuplaSignal.connect(self.iniciar_extracao_dupla)
        self.model.tabelaCarregada.connect(self.configurar_sql_model)

    def iniciar_extracao_dupla(self, caminho_tr, caminho_homolog):
        """Orquestra a extração do TR e a extração da Homologação."""
        # 1. Extração síncrona do Termo de Referência
        self.df_tr_temp = self.view.tr_widget.extrair_dados_tr(caminho_tr)
        
        if self.df_tr_temp.empty:
            QMessageBox.warning(self.view, "Erro", "Não foi possível extrair dados estruturados do Termo de Referência.")
            return

        # 2. Configura a barra de progresso Popup para o Worker da Homologação
        self.progress_dialog = QProgressDialog("Lendo Termos de Homologação...", "Cancelar", 0, 100, self.view)
        self.progress_dialog.setWindowTitle("Processamento")
        self.progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
        self.progress_dialog.setAutoClose(True)
        self.progress_dialog.setValue(0)

        # 3. Inicia a Thread para ler os múltiplos PDFs de Homologação
        self.worker = Worker(pdf_dir=Path(caminho_homolog), modo='completo')
        self.worker.progress_signal.connect(self.progress_dialog.setValue)
        self.worker.processing_complete.connect(self.finalizar_extracao_dupla)
        self.worker.start()

    def finalizar_extracao_dupla(self, extracted_data):
        """Mescla os resultados e salva no banco de dados."""
        self.progress_dialog.setValue(100)

        if not extracted_data:
            QMessageBox.warning(self.view, "Aviso", "Nenhum arquivo PDF foi encontrado na pasta de Homologação.")
            return

        try:
            df_homolog = save_to_dataframe(extracted_data)
        except ValueError as e:
            QMessageBox.warning(self.view, "Erro de Extração", f"O sistema não encontrou itens válidos de Homologação.\n\nDetalhe técnico: {e}")
            return
        except Exception as e:
            QMessageBox.critical(self.view, "Erro Crítico", f"Falha ao processar os Termos de Homologação: {e}")
            return

        if df_homolog.empty:
            QMessageBox.warning(self.view, "Aviso", "Nenhum item válido retornado da Homologação.")
            return

        # Limpeza para garantir cruzamento exato das chaves (número do item)
        df_homolog['item'] = df_homolog['item'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()
        self.df_tr_temp['item'] = self.df_tr_temp['item'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()

        # MESCLAGEM: O Homologação traz a DESCRIÇÃO e valores. O TR traz o CATÁLOGO e a ESPECIFICAÇÃO (Descrição Detalhada).
        df_final = pd.merge(df_homolog, self.df_tr_temp, on='item', how='left')

        self.atualizar_banco_com_df(df_final)
        QMessageBox.information(self.view, "Sucesso", "Dados cruzados com sucesso!")

    def atualizar_banco_com_df(self, df):
        if df.empty:
            return

        # Limpa o banco antes da inserção
        num_rows = self.model.rowCount()
        for i in range(num_rows - 1, -1, -1):
            self.model.removeRow(i)
        self.model.submitAll()

        # O modelo SQL tem um array de column_names já programado no seu model.py
        db_columns = self.model.column_names

        # Insere o DataFrame cruzado respeitando as colunas do Banco
        for index, row in df.iterrows():
            record = self.model.record()
            for col in db_columns:
                if col in df.columns and pd.notna(row[col]):
                    record.setValue(col, str(row[col]))
            
            self.model.insertRecord(-1, record)
        
        if self.model.submitAll():
            self.model.select() 
        else:
            print(f"Erro ao salvar no banco: {self.model.lastError().text()}")

    def limpar_tabela(self):
        resposta = QMessageBox.question(self.view.tr_widget, "Confirmar Limpeza", "Tem certeza de que deseja apagar todos os itens da tabela atual?\nIsso não pode ser desfeito.", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if resposta == QMessageBox.StandardButton.Yes:
            num_rows = self.model.rowCount()
            for i in range(num_rows - 1, -1, -1):
                self.model.removeRow(i)
            if self.model.submitAll():
                self.model.select()  
            else:
                QMessageBox.warning(self.view.tr_widget, "Erro", f"Erro ao limpar banco de dados: {self.model.lastError().text()}")

    def configurar_sql_model(self):
        self.view.tr_widget.table_view.setModel(self.model)
        self.view.configurar_visualizacao_tabela_tr(self.view.tr_widget.table_view)

    def instrucoes(self):
        self.view.content_area.setCurrentWidget(self.view.instrucoes_widget)

    def termo_referencia(self):
        self.view.content_area.setCurrentWidget(self.view.tr_widget)
        self.view.tr_widget.table_view.setModel(self.model)
        self.view.configurar_visualizacao_tabela_tr(self.view.tr_widget.table_view)

    def sicaf_widget(self):
        self.view.content_area.setCurrentWidget(self.view.sicaf_widget)

    def gerar_atas(self):
        self.view.content_area.setCurrentWidget(self.view.atas_widget)